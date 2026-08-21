from __future__ import annotations

from pathlib import Path

import pytest

from backend.anomaly import FEATURE_NAMES, CommandAnomalyDetector


def test_missing_artifact_falls_back(tmp_path: Path):
    detector = CommandAnomalyDetector(
        model_path=tmp_path / "missing.joblib",
        meta_path=tmp_path / "missing.json",
    )
    assert detector.degraded is True
    assert detector.artifact_verified is False
    risk, _, info = detector.score(
        speed=0.8,
        known_device=True,
        restricted_destination=False,
        commands_last_10_seconds=1,
        previous_failures=0,
    )
    assert 0.0 < risk < 1.0
    assert info["degraded"] is True


def test_schema_mismatch_falls_back(tmp_path: Path, monkeypatch):
    # Point at real model but corrupt meta feature names via custom detector paths.
    root = Path(__file__).resolve().parents[1]
    model = root / "artifacts" / "command_anomaly_iforest.joblib"
    meta = tmp_path / "bad_meta.json"
    meta.write_text(
        '{"feature_names":["speed"],"model_version":"bad","n_training_samples":1}'
    )
    detector = CommandAnomalyDetector(model_path=model, meta_path=meta)
    assert detector.degraded is True or detector.feature_names == FEATURE_NAMES
