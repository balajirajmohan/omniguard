#!/usr/bin/env python3
"""Train action-window IsolationForest on normal sequences only."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.action_anomaly import FEATURE_NAMES, risk_from_raw  # noqa: E402

ART = ROOT / "artifacts"
MODEL_PATH = ART / "action_window_iforest.joblib"
META_PATH = ART / "action_window_meta.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    from scripts.generate_action_sequences import main as gen

    gen()
    normal = np.loadtxt(
        ART / "action_window_normal.csv", delimiter=",", skiprows=1
    )
    eval_rows = list(
        open(ART / "action_window_eval.csv", encoding="utf-8")
    )[1:]

    model = IsolationForest(
        n_estimators=160, contamination=0.04, random_state=21
    )
    model.fit(normal)
    joblib.dump(model, MODEL_PATH)

    results = []
    tp = fp = tn = fn = 0
    for line in eval_rows:
        parts = line.strip().split(",")
        label = int(float(parts[0]))
        feats = np.asarray([[float(x) for x in parts[1 : 1 + len(FEATURE_NAMES)]]])
        scenario = parts[-1]
        raw = float(model.decision_function(feats)[0])
        risk = risk_from_raw(raw)
        pred = risk >= 0.80
        if pred and label == 1:
            tp += 1
        elif pred and label == 0:
            fp += 1
        elif (not pred) and label == 0:
            tn += 1
        else:
            fn += 1
        results.append(
            {
                "scenario": scenario,
                "label": label,
                "predicted_anomaly": pred,
                "risk": risk,
                "raw_score": raw,
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    meta = {
        "model_name": "IsolationForest",
        "model_version": "action-window-iforest-v1",
        "feature_names": FEATURE_NAMES,
        "trained_on": "synthetic_normal_action_windows_only",
        "dataset_label": "synthetic",
        "n_training_samples": int(normal.shape[0]),
        "n_eval_samples": len(results),
        "contamination": 0.04,
        "random_state": 21,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "critical_risk_threshold": 0.80,
        "warning_risk_threshold": 0.60,
        "model_sha256": sha256_file(MODEL_PATH),
        "dependency_versions": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "numpy": np.__version__,
            "scikit_learn": __import__("sklearn").__version__,
            "joblib": joblib.__version__,
        },
        "eval_metrics": {
            "precision": precision,
            "recall": recall,
            "false_positive_rate": fpr,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "note": "Eval includes valid-identity malicious manipulation windows. Not production validation.",
        },
        "eval_results": results,
        "judge_note": (
            "anomaly_risk_score is an IsolationForest anomaly score, not an attack probability. "
            "model_confidence is null (uncalibrated)."
        ),
    }
    META_PATH.write_text(json.dumps(meta, indent=2))
    print(f"wrote {MODEL_PATH}")
    print(f"wrote {META_PATH}")
    print(f"eval precision={precision:.2f} recall={recall:.2f} fpr={fpr:.2f}")


if __name__ == "__main__":
    main()
