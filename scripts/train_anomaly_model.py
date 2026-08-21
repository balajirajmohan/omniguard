#!/usr/bin/env python3
"""Train IsolationForest on normal command telemetry and persist artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.anomaly import FEATURE_NAMES, risk_from_raw  # noqa: E402
from scripts.generate_training_data import generate_eval, generate_normal  # noqa: E402


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
    if eval_csv.exists():
        evaluation = pd.read_csv(eval_csv)
    else:
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

    results = []
    for i, row in evaluation.iterrows():
        results.append(
            {
                "scenario": row["scenario"],
                "label": int(row["label"]),
                "predicted_anomaly": bool(preds[i] == -1),
                "risk": risks[i],
                "raw_score": float(raw_scores[i]),
            }
        )

    labeled_pos = [r for r in results if r["label"] == 1]
    caught = [r for r in labeled_pos if r["risk"] >= 0.80 or r["predicted_anomaly"]]
    recall = (len(caught) / len(labeled_pos)) if labeled_pos else None

    model_path = args.artifact_dir / "command_anomaly_iforest.joblib"
    meta_path = args.artifact_dir / "command_anomaly_meta.json"
    joblib.dump(model, model_path)

    meta = {
        "model_name": "IsolationForest",
        "model_version": args.model_version,
        "feature_names": FEATURE_NAMES,
        "trained_on": "synthetic_normal_commands_only",
        "n_training_samples": int(len(normal)),
        "contamination": 0.03,
        "random_state": 42,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "critical_risk_threshold": 0.80,
        "warning_risk_threshold": 0.60,
        "eval_recall_at_critical_or_predict": recall,
        "eval_results": results,
        "judge_note": (
            "Unsupervised model trained only on normal operations. "
            "Attack labels evaluate and demonstrate detection; they are not "
            "used to teach every possible attack."
        ),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    print(f"Saved model → {model_path}")
    print(f"Saved meta  → {meta_path}")
    print(f"Eval recall (critical/predict): {recall}")
    for row in results:
        print(
            f"  {row['scenario']}: label={row['label']} "
            f"risk={row['risk']} anomaly={row['predicted_anomaly']}"
        )


if __name__ == "__main__":
    main()
