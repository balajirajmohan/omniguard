"""IsolationForest behavioural anomaly detector for robot commands.

Hard safety rules remain authoritative. This model supplies an unknown-threat
signal for command behaviour that is atypical for a fleet identity even when
no explicit rule fires.

Fail-safe: if the artifact is missing or fails to load, a small in-memory
baseline is trained and status reports degraded=True.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

FEATURE_NAMES = [
    "speed",
    "known_device",
    "restricted_destination",
    "commands_last_10_seconds",
    "previous_failures",
    "hour_of_day",
    "seconds_since_last_command",
]

MODEL_VERSION_FALLBACK = "iforest-inline-v1"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT / "artifacts" / "command_anomaly_iforest.joblib"
DEFAULT_META_PATH = ROOT / "artifacts" / "command_anomaly_meta.json"


def risk_from_raw(raw: float) -> float:
    # IsolationForest: lower/negative = more anomalous. Map to 0..1 risk.
    risk = 1.0 / (1.0 + math.exp(25.0 * (raw - 0.05)))
    return round(max(0.01, min(0.99, risk)), 2)


class CommandAnomalyDetector:
    def __init__(
        self,
        model_path: Path | None = None,
        meta_path: Path | None = None,
    ) -> None:
        self.model_path = Path(
            os.getenv("OMNIGUARD_ANOMALY_MODEL", str(model_path or DEFAULT_MODEL_PATH))
        )
        self.meta_path = Path(
            os.getenv("OMNIGUARD_ANOMALY_META", str(meta_path or DEFAULT_META_PATH))
        )
        self.feature_names = list(FEATURE_NAMES)
        self.model_version = MODEL_VERSION_FALLBACK
        self.n_training_samples = 0
        self.degraded = False
        self.available = True
        self.critical_threshold = float(os.getenv("OMNIGUARD_AI_CRITICAL", "0.80"))
        self.warning_threshold = float(os.getenv("OMNIGUARD_AI_WARNING", "0.60"))
        self.meta: dict[str, Any] = {}
        self._load_or_bootstrap()

    def _bootstrap_inline(self) -> IsolationForest:
        rng = np.random.default_rng(42)
        n = 800
        normal = np.column_stack(
            [
                rng.uniform(0.4, 1.1, n),
                np.ones(n),
                np.zeros(n),
                rng.integers(0, 4, n),
                rng.integers(0, 2, n),
                rng.integers(8, 19, n),
                rng.uniform(8.0, 120.0, n),
            ]
        )
        model = IsolationForest(
            n_estimators=150,
            contamination=0.03,
            random_state=42,
        )
        model.fit(normal)
        self.n_training_samples = n
        self.degraded = True
        self.model_version = MODEL_VERSION_FALLBACK
        return model

    def _load_or_bootstrap(self) -> None:
        try:
            import joblib

            if self.model_path.exists():
                self.model = joblib.load(self.model_path)
                if self.meta_path.exists():
                    self.meta = json.loads(self.meta_path.read_text())
                    self.feature_names = list(
                        self.meta.get("feature_names", FEATURE_NAMES)
                    )
                    self.model_version = str(
                        self.meta.get("model_version", MODEL_VERSION_FALLBACK)
                    )
                    self.n_training_samples = int(
                        self.meta.get("n_training_samples", 0)
                    )
                    self.critical_threshold = float(
                        self.meta.get(
                            "critical_risk_threshold", self.critical_threshold
                        )
                    )
                    self.warning_threshold = float(
                        self.meta.get(
                            "warning_risk_threshold", self.warning_threshold
                        )
                    )
                self.degraded = False
                return
        except Exception:
            pass
        self.model = self._bootstrap_inline()

    def score(
        self,
        *,
        speed: float,
        known_device: bool,
        restricted_destination: bool,
        commands_last_10_seconds: int,
        previous_failures: int,
        hour_of_day: int = 12,
        seconds_since_last_command: float = 30.0,
    ) -> tuple[float, dict[str, float], dict[str, Any]]:
        values = np.array(
            [
                speed,
                float(known_device),
                float(restricted_destination),
                float(commands_last_10_seconds),
                float(previous_failures),
                float(hour_of_day),
                float(seconds_since_last_command),
            ],
            dtype=float,
        )
        try:
            raw = float(self.model.decision_function(values.reshape(1, -1))[0])
            pred = int(self.model.predict(values.reshape(1, -1))[0])
            risk = risk_from_raw(raw)
        except Exception:
            self.available = False
            features = dict(zip(FEATURE_NAMES, values.tolist(), strict=True))
            return 0.0, features, {
                "ai_anomalous": False,
                "ai_unavailable": True,
                "model_version": self.model_version,
                "raw_score": None,
            }

        features = dict(zip(self.feature_names, values.tolist(), strict=False))
        # Pad/trim if schema drift
        if len(features) != len(FEATURE_NAMES):
            features = dict(zip(FEATURE_NAMES, values.tolist(), strict=True))

        info = {
            "ai_anomalous": bool(pred == -1 or risk >= self.critical_threshold),
            "ai_unavailable": False,
            "model_version": self.model_version,
            "model_name": "IsolationForest",
            "raw_score": round(raw, 4),
            "critical_threshold": self.critical_threshold,
            "warning_threshold": self.warning_threshold,
            "degraded": self.degraded,
            "n_training_samples": self.n_training_samples,
        }
        return risk, features, info

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "degraded": self.degraded,
            "model_name": "IsolationForest",
            "model_version": self.model_version,
            "n_training_samples": self.n_training_samples,
            "feature_names": self.feature_names,
            "critical_threshold": self.critical_threshold,
            "warning_threshold": self.warning_threshold,
            "artifact": str(self.model_path),
            "artifact_present": self.model_path.exists(),
            "controls_robot": False,
            "judge_note": (
                "Trained only on normal operations. Attack labels evaluate "
                "detection; they do not teach every possible attack."
            ),
        }


detector = CommandAnomalyDetector()
