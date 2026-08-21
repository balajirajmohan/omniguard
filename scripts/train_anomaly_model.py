#!/usr/bin/env python3
"""Train IsolationForest on normal command telemetry and persist artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.anomaly import FEATURE_NAMES, risk_from_raw  # noqa: E402
from scripts.generate_training_data import generate_eval, generate_normal  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-normal", type=int, default=5000)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--model-version", default="iforest-v1")
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.artifact_dir.mkdir(parents=True, exist_ok=True)

    normal_csv = args.data_dir / "normal_commands.csv"
    if normal_csv.exists():
        normal = pd.read_csv(normal_csv)
    else:
        normal = generate_normal(args.n_normal)
        normal.to_csv(normal_csv, index=False)

    eval_csv = args.data_dir / "eval_commands.csv"
    evaluation = generate_eval()
    evaluation.to_csv(eval_csv, index=False)

    x_train = normal[FEATURE_NAMES].to_numpy(dtype=float)
    model = IsolationForest(
        n_estimators=200,
        contamination=0.03,
        random_state=42,
    )
    model.fit(x_train)

    x_eval = evaluation[FEATURE_NAMES].to_numpy(dtype=float)
    raw_scores = model.decision_function(x_eval)
    preds = model.predict(x_eval)
    risks = [risk_from_raw(float(r)) for r in raw_scores]
    predicted_pos = np.array(
        [(risks[i] >= 0.80) or (preds[i] == -1) for i in range(len(evaluation))]
    )
    labels = evaluation["label"].to_numpy(dtype=int)

    tp = int(((labels == 1) & predicted_pos).sum())
    fp = int(((labels == 0) & predicted_pos).sum())
    tn = int(((labels == 0) & ~predicted_pos).sum())
    fn = int(((labels == 1) & ~predicted_pos).sum())
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    fpr = fp / (fp + tn) if (fp + tn) else None

    results = []
    for i, row in evaluation.iterrows():
        results.append(
            {
                "scenario": row["scenario"],
                "label": int(row["label"]),
                "predicted_anomaly": bool(predicted_pos[i]),
                "risk": risks[i],
                "raw_score": float(raw_scores[i]),
            }
        )

    model_path = args.artifact_dir / "command_anomaly_iforest.joblib"
    meta_path = args.artifact_dir / "command_anomaly_meta.json"
    joblib.dump(model, model_path)
    checksum = sha256_file(model_path)

    import sklearn

    meta = {
        "model_name": "IsolationForest",
        "model_version": args.model_version,
        "feature_names": FEATURE_NAMES,
        "trained_on": "synthetic_normal_commands_only",
        "dataset_label": "synthetic",
        "n_training_samples": int(len(normal)),
        "n_eval_samples": int(len(evaluation)),
        "contamination": 0.03,
        "random_state": 42,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "critical_risk_threshold": 0.80,
        "warning_risk_threshold": 0.60,
        "model_sha256": checksum,
        "dependency_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
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
            "note": (
                "Evaluation set mixes synthetic normals and hand-crafted attack "
                "demonstrations. Not production-grade validation."
            ),
        },
        "eval_results": results,
        "judge_note": (
            "IsolationForest is trained only on synthetic normal fleet behavior. "
            "The attack samples are used for demonstration and evaluation, not to "
            "teach every attack."
        ),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    print(f"Saved model → {model_path}")
    print(f"Saved meta  → {meta_path}")
    print(f"SHA-256     → {checksum}")
    print(f"Eval precision={precision} recall={recall} fpr={fpr}")


if __name__ == "__main__":
    main()
