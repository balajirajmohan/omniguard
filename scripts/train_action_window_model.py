#!/usr/bin/env python3
"""Train action-window IsolationForest on normal sequences only.

Thresholds come from held-out normal-score quantiles. Eval reports both
IsolationForest-only metrics and the production hybrid pipeline
(effective_risk = max(ml, behavioral_rule)).
"""

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

from backend.action_anomaly import (  # noqa: E402
    FEATURE_NAMES,
    ActionWindowAnomalyDetector,
    risk_from_raw,
)

ART = ROOT / "artifacts"
MODEL_PATH = ART / "action_window_iforest.joblib"
META_PATH = ART / "action_window_meta.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metrics(preds: list[bool], labels: list[int]) -> dict[str, float | int]:
    tp = fp = tn = fn = 0
    for pred, label in zip(preds, labels):
        if pred and label == 1:
            tp += 1
        elif pred and label == 0:
            fp += 1
        elif (not pred) and label == 0:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "false_positive_rate": fpr,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def main() -> None:
    from scripts.generate_action_sequences import main as gen

    gen()
    normal = np.loadtxt(
        ART / "action_window_normal.csv", delimiter=",", skiprows=1
    )
    eval_rows = list(
        open(ART / "action_window_eval.csv", encoding="utf-8")
    )[1:]

    rng = np.random.default_rng(21)
    order = rng.permutation(normal.shape[0])
    split = int(0.8 * normal.shape[0])
    train = normal[order[:split]]
    held = normal[order[split:]]

    model = IsolationForest(
        n_estimators=160, contamination=0.04, random_state=21
    )
    model.fit(train)
    joblib.dump(model, MODEL_PATH)

    held_risks = [
        risk_from_raw(float(model.decision_function([row])[0])) for row in held
    ]
    quantile_warning = float(np.quantile(held_risks, 0.95))
    quantile_critical = float(np.quantile(held_risks, 0.99))
    # Operational floors: isolated legal arm/gripper moves must not enter the
    # HOLD band. Quantiles remain the statistical source; floors are documented.
    warning = round(max(quantile_warning, 0.60), 2)
    critical = round(max(quantile_critical, 0.80), 2)
    if critical <= warning:
        critical = round(min(0.95, warning + 0.15), 2)

    labels: list[int] = []
    ml_preds: list[bool] = []
    hybrid_preds: list[bool] = []
    results = []
    for line in eval_rows:
        parts = line.strip().split(",")
        label = int(float(parts[0]))
        feat_vals = [float(x) for x in parts[1 : 1 + len(FEATURE_NAMES)]]
        feats = np.asarray([feat_vals])
        feature_dict = dict(zip(FEATURE_NAMES, feat_vals))
        scenario = parts[-1]
        raw = float(model.decision_function(feats)[0])
        ml_risk = risk_from_raw(raw)
        rule = ActionWindowAnomalyDetector.behavioral_rule_score(feature_dict)
        effective = max(ml_risk, rule)
        ml_pred = ml_risk >= critical
        hybrid_pred = effective >= critical
        labels.append(label)
        ml_preds.append(ml_pred)
        hybrid_preds.append(hybrid_pred)
        results.append(
            {
                "scenario": scenario,
                "label": label,
                "ml_risk": ml_risk,
                "behavioral_rule_score": rule,
                "effective_risk": effective,
                "predicted_anomaly_ml": ml_pred,
                "predicted_anomaly_hybrid": hybrid_pred,
                "raw_score": raw,
            }
        )

    ml_metrics = _metrics(ml_preds, labels)
    hybrid_metrics = _metrics(hybrid_preds, labels)

    meta = {
        "model_name": "IsolationForest",
        "model_version": "action-window-iforest-v1",
        "feature_names": FEATURE_NAMES,
        "trained_on": "synthetic_normal_action_windows_only",
        "dataset_label": "synthetic",
        "n_training_samples": int(train.shape[0]),
        "n_heldout_normal_samples": int(held.shape[0]),
        "n_eval_samples": len(results),
        "contamination": 0.04,
        "random_state": 21,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "threshold_method": "heldout_normal_quantiles_with_operational_floors",
        "warning_quantile": 0.95,
        "critical_quantile": 0.99,
        "quantile_warning_raw": round(quantile_warning, 2),
        "quantile_critical_raw": round(quantile_critical, 2),
        "operational_warning_floor": 0.60,
        "operational_critical_floor": 0.80,
        "critical_risk_threshold": critical,
        "warning_risk_threshold": warning,
        "heldout_normal_risk_summary": {
            "min": round(float(min(held_risks)), 2),
            "p50": round(float(np.quantile(held_risks, 0.50)), 2),
            "p95": round(quantile_warning, 2),
            "p99": round(quantile_critical, 2),
            "max": round(float(max(held_risks)), 2),
        },
        "model_sha256": sha256_file(MODEL_PATH),
        "dependency_versions": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "numpy": np.__version__,
            "scikit_learn": __import__("sklearn").__version__,
            "joblib": joblib.__version__,
        },
        "eval_metrics_ml_only": {
            **ml_metrics,
            "note": (
                "IsolationForest alone against eval labels. "
                "Does not include the deterministic behavioral rule."
            ),
        },
        "eval_metrics_production_pipeline": {
            **hybrid_metrics,
            "note": (
                "Production decision uses effective_risk = max(ml, behavioral_rule). "
                "Not live Isaac/GPU validation."
            ),
        },
        "eval_metrics": {
            **hybrid_metrics,
            "note": (
                "Alias of eval_metrics_production_pipeline for backward compatibility."
            ),
        },
        "eval_results": results,
        "judge_note": (
            "anomaly_risk_score is IsolationForest-only (not attack probability). "
            "behavioral_rule_score is a separate deterministic burst rule. "
            "effective_risk drives HOLD/BLOCK. model_confidence is null (uncalibrated)."
        ),
    }
    META_PATH.write_text(json.dumps(meta, indent=2))
    print(f"wrote {MODEL_PATH}")
    print(f"wrote {META_PATH}")
    print(
        f"thresholds warning={warning:.2f} critical={critical:.2f} "
        f"(held-out normal quantiles)"
    )
    print(
        f"ml-only precision={ml_metrics['precision']:.2f} "
        f"recall={ml_metrics['recall']:.2f}"
    )
    print(
        f"hybrid precision={hybrid_metrics['precision']:.2f} "
        f"recall={hybrid_metrics['recall']:.2f}"
    )


if __name__ == "__main__":
    main()
