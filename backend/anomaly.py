"""IsolationForest behavioural anomaly detector with artifact integrity checks."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import warnings
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
    risk = 1.0 / (1.0 + math.exp(25.0 * (raw - 0.05)))
    return round(max(0.01, min(0.99, risk)), 2)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        self.artifact_verified = False
        self.artifact_sha256: str | None = None
        self.load_error: str | None = None
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
        self.artifact_verified = False
        self.model_version = MODEL_VERSION_FALLBACK
        return model

    def _validate_schema(self) -> None:
        names = list(self.meta.get("feature_names", FEATURE_NAMES))
        if names != FEATURE_NAMES:
            raise ValueError(
                f"feature schema mismatch: expected {FEATURE_NAMES}, got {names}"
            )
        if len(names) != len(FEATURE_NAMES):
            raise ValueError("feature count mismatch")

    def _load_or_bootstrap(self) -> None:
        try:
            import joblib

            trusted_root = (ROOT / "artifacts").resolve()
            model_resolved = self.model_path.resolve()
            if trusted_root not in model_resolved.parents and model_resolved.parent != trusted_root:
                raise ValueError("model path must be under repository artifacts/")

            if self.model_path.exists():
                self.artifact_sha256 = sha256_file(self.model_path)
                if self.meta_path.exists():
                    self.meta = json.loads(self.meta_path.read_text())
                    self._validate_schema()
                    expected = self.meta.get("model_sha256")
                    if expected and expected != self.artifact_sha256:
                        raise ValueError("model checksum mismatch")
                    self.feature_names = list(FEATURE_NAMES)
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

                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message="Setting the shape on a NumPy array has been deprecated",
                        category=DeprecationWarning,
                    )
                    self.model = joblib.load(self.model_path)

                n_features = getattr(self.model, "n_features_in_", len(FEATURE_NAMES))
                if int(n_features) != len(FEATURE_NAMES):
                    raise ValueError(
                        f"model expects {n_features} features, schema has {len(FEATURE_NAMES)}"
                    )
                self.degraded = False
                self.artifact_verified = True
                return
            self.load_error = "artifact missing"
        except Exception as exc:  # noqa: BLE001
            self.load_error = str(exc)
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
            "artifact_verified": self.artifact_verified,
            "n_training_samples": self.n_training_samples,
        }
        return risk, features, info

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "degraded": self.degraded,
            "artifact_verified": self.artifact_verified,
            "artifact_sha256": self.artifact_sha256,
            "load_error": self.load_error,
            "model_name": "IsolationForest",
            "model_version": self.model_version,
            "n_training_samples": self.n_training_samples,
            "feature_names": self.feature_names,
            "critical_threshold": self.critical_threshold,
            "warning_threshold": self.warning_threshold,
            "artifact": str(self.model_path),
            "artifact_present": self.model_path.exists(),
            "dataset_label": "synthetic_normal_commands_only",
            "runtime_versions": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
            },
            "eval_metrics": self.meta.get("eval_metrics"),
            "controls_robot": False,
            "judge_note": (
                "IsolationForest is trained only on synthetic normal fleet behavior. "
                "Attack samples are used for demonstration and evaluation, not to "
                "teach every attack."
            ),
        }


detector = CommandAnomalyDetector()
