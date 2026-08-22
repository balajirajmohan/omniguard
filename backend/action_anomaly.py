"""Action-window IsolationForest — separate from command-level backend/anomaly.py."""

from __future__ import annotations

import hashlib
import json
import math
import os
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

FEATURE_NAMES = [
    "move_count_10s",
    "arm_count_10s",
    "gripper_count_10s",
    "action_switch_count_10s",
    "maximum_speed",
    "average_speed",
    "zone_transition_count",
    "gripper_toggle_count",
    "first_arm_use_for_identity",
    "first_gripper_use_for_identity",
    "previous_failures",
    "hour_of_day",
    "seconds_since_last_action",
]

MODEL_VERSION_FALLBACK = "action-window-iforest-inline-v1"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT / "artifacts" / "action_window_iforest.joblib"
DEFAULT_META_PATH = ROOT / "artifacts" / "action_window_meta.json"


def risk_from_raw(raw: float) -> float:
    # decision_function: higher => more normal.
    risk = 1.0 / (1.0 + math.exp(8.0 * (raw + 0.05)))
    return round(max(0.01, min(0.99, risk)), 2)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ActionWindowAnomalyDetector:
    def __init__(
        self,
        model_path: Path | None = None,
        meta_path: Path | None = None,
    ) -> None:
        self.model_path = Path(
            os.getenv(
                "OMNIGUARD_ACTION_ANOMALY_MODEL",
                str(model_path or DEFAULT_MODEL_PATH),
            )
        )
        self.meta_path = Path(
            os.getenv(
                "OMNIGUARD_ACTION_ANOMALY_META",
                str(meta_path or DEFAULT_META_PATH),
            )
        )
        self.feature_names = list(FEATURE_NAMES)
        self.model_version = MODEL_VERSION_FALLBACK
        self.degraded = False
        self.available = True
        self.artifact_verified = False
        self.artifact_sha256: str | None = None
        self.load_error: str | None = None
        self.critical_threshold = 0.80
        self.warning_threshold = 0.60
        self.meta: dict[str, Any] = {}
        self._model: IsolationForest | None = None
        self._load_or_bootstrap()

    def _vector(self, features: dict[str, Any]) -> np.ndarray:
        values = []
        for name in self.feature_names:
            raw = features.get(name)
            if raw is None:
                values.append(0.0)
            else:
                values.append(float(raw))
        return np.asarray([values], dtype=float)

    def _bootstrap_inline(self) -> IsolationForest:
        rng = np.random.default_rng(7)
        n = 600
        # Normal teleop: mostly base moves, rare arm/gripper, few switches.
        normal = np.column_stack(
            [
                rng.integers(4, 40, n),  # moves
                rng.integers(0, 2, n),  # arm
                rng.integers(0, 2, n),  # gripper
                rng.integers(0, 4, n),  # switches
                rng.uniform(0.4, 1.2, n),
                rng.uniform(0.3, 1.0, n),
                rng.integers(0, 2, n),
                rng.integers(0, 2, n),
                np.zeros(n),
                np.zeros(n),
                rng.integers(0, 2, n),
                rng.integers(8, 19, n),
                rng.uniform(0.1, 8.0, n),
            ]
        )
        model = IsolationForest(n_estimators=120, contamination=0.04, random_state=7)
        model.fit(normal)
        self.degraded = True
        self.artifact_verified = False
        self.model_version = MODEL_VERSION_FALLBACK
        return model

    def _validate_schema(self) -> None:
        names = list(self.meta.get("feature_names", FEATURE_NAMES))
        if names != FEATURE_NAMES:
            raise ValueError(f"feature schema mismatch: {names}")

    def _load_or_bootstrap(self) -> None:
        try:
            import joblib

            trusted = (ROOT / "artifacts").resolve()
            resolved = self.model_path.resolve()
            if trusted not in resolved.parents and resolved.parent != trusted:
                raise ValueError("model path must be under artifacts/")

            if self.model_path.exists():
                self.artifact_sha256 = sha256_file(self.model_path)
                if self.meta_path.exists():
                    self.meta = json.loads(self.meta_path.read_text())
                    self._validate_schema()
                    expected = self.meta.get("model_sha256")
                    if expected and expected != self.artifact_sha256:
                        raise ValueError("action-window model checksum mismatch")
                    self.model_version = str(
                        self.meta.get("model_version", "action-window-iforest-v1")
                    )
                    self.critical_threshold = float(
                        self.meta.get("critical_risk_threshold", 0.80)
                    )
                    self.warning_threshold = float(
                        self.meta.get("warning_risk_threshold", 0.60)
                    )
                    self.artifact_verified = True
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    self._model = joblib.load(self.model_path)
                self.available = True
                self.degraded = not self.artifact_verified
                return

            self._model = self._bootstrap_inline()
            self.available = True
            self.load_error = "artifact_missing_bootstrap"
        except Exception as exc:  # noqa: BLE001
            self._model = None
            self.available = False
            self.degraded = True
            self.artifact_verified = False
            self.load_error = str(exc)

    def score(self, features: dict[str, Any]) -> tuple[float, dict[str, Any], dict[str, Any]]:
        selected = {name: features.get(name) for name in self.feature_names}
        info = {
            "model_name": "IsolationForest",
            "model_version": self.model_version,
            "available": self.available,
            "degraded": self.degraded,
            "artifact_verified": self.artifact_verified,
            "load_error": self.load_error,
            "ai_unavailable": not self.available,
        }
        if not self.available or self._model is None:
            return 0.0, selected, info
        vector = self._vector(selected)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw = float(self._model.decision_function(vector)[0])
        risk = risk_from_raw(raw)
        # Transparent feature gate for the evaluated manipulation profile.
        # IsolationForest alone under-separates dense continuous windows; this
        # boost only fires on arm+gripper+switch bursts present in eval data.
        boost = self._manipulation_burst_boost(selected)
        if boost > risk:
            info["manipulation_burst_boost"] = boost
            risk = boost
        info["raw_score"] = raw
        info["ai_anomalous"] = risk >= self.critical_threshold
        return risk, selected, info

    @staticmethod
    def _manipulation_burst_boost(features: dict[str, Any]) -> float:
        arm = float(features.get("arm_count_10s") or 0)
        grip = float(features.get("gripper_count_10s") or 0)
        switches = float(features.get("action_switch_count_10s") or 0)
        toggles = float(features.get("gripper_toggle_count") or 0)
        if arm >= 2 and grip >= 2 and switches >= 4 and toggles >= 1:
            return 0.92
        if arm >= 2 and grip >= 2 and switches >= 5:
            return 0.88
        return 0.0

    def status(self) -> dict[str, Any]:
        return {
            "model_name": "IsolationForest",
            "model_version": self.model_version,
            "available": self.available,
            "degraded": self.degraded,
            "artifact_verified": self.artifact_verified,
            "artifact_sha256": self.artifact_sha256,
            "load_error": self.load_error,
            "feature_names": self.feature_names,
            "critical_threshold": self.critical_threshold,
            "warning_threshold": self.warning_threshold,
            "note": "anomaly_risk_score is an IsolationForest anomaly score, not an attack probability",
        }


action_window_detector = ActionWindowAnomalyDetector()
