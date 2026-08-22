#!/usr/bin/env python3
"""Export reviewed incidents into a candidate training dataset (no auto-promote)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path_note = """
Promotion path (manual only):
  1. candidate training
  2. offline evaluation
  3. shadow deployment
  4. comparison against current model
  5. human approval
  6. promotion or rejection

This script never retrains or deploys automatically.
"""


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    from backend.incident_store import FEEDBACK, incident_store

    out_dir = ROOT / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"training_candidates_{stamp}.csv"
    rows = []
    for incident in incident_store.list(limit=500):
        if incident.get("status") not in {"RESOLVED", "FALSE_POSITIVE"}:
            continue
        feedback = incident.get("human_feedback") or {}
        label = feedback.get("classification")
        if label not in FEEDBACK:
            continue
        features = (incident.get("ai_evidence") or {}).get("anomaly_features") or {}
        rows.append(
            {
                "incident_id": incident["incident_id"],
                "label": label,
                "decision_source": incident.get("decision_source"),
                "model_version": incident.get("model_version"),
                "policy_version": incident.get("policy_version"),
                "features_json": json.dumps(features),
            }
        )

    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "incident_id",
                "label",
                "decision_source",
                "model_version",
                "policy_version",
                "features_json",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    guide = out_dir / "TRAINING_PROMOTION.md"
    guide.write_text(sys_path_note.strip() + "\n")
    print(f"wrote {out} ({len(rows)} rows)")
    print(f"wrote {guide}")


if __name__ == "__main__":
    main()
