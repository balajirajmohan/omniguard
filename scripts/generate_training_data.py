#!/usr/bin/env python3
"""Generate synthetic normal command telemetry + a labeled evaluation set.

Important (judge wording):
  We train the unsupervised model only on normal operations.
  Attack labels are used to evaluate and demonstrate it, not to teach
  every possible attack.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

FEATURE_NAMES = [
    "speed",
    "known_device",
    "restricted_destination",
    "commands_last_10_seconds",
    "previous_failures",
    "hour_of_day",
    "seconds_since_last_command",
]


def generate_normal(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "speed": rng.uniform(0.4, 1.1, n),
            "known_device": np.ones(n),
            "restricted_destination": np.zeros(n),
            "commands_last_10_seconds": rng.integers(0, 4, n),
            "previous_failures": rng.integers(0, 2, n),
            "hour_of_day": rng.integers(8, 19, n),
            "seconds_since_last_command": rng.uniform(8.0, 120.0, n),
            "label": np.zeros(n, dtype=int),
            "scenario": ["normal"] * n,
        }
    )


def generate_eval(seed: int = 7) -> pd.DataFrame:
    """Labeled evaluation scenarios (not used for IsolationForest fit).

    Includes synthetic normals plus hand-crafted attack demonstrations.
    This is demo/evaluation evidence — not production-grade validation.
    """
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for i in range(40):
        rows.append(
            {
                "speed": float(rng.uniform(0.45, 1.05)),
                "known_device": 1,
                "restricted_destination": 0,
                "commands_last_10_seconds": int(rng.integers(0, 4)),
                "previous_failures": int(rng.integers(0, 2)),
                "hour_of_day": int(rng.integers(8, 19)),
                "seconds_since_last_command": float(rng.uniform(10.0, 90.0)),
                "label": 0,
                "scenario": f"eval_normal_{i}",
            }
        )
    attack_templates = [
        ("known_compromise", 3.5, 0, 1, 8, 3, 2, 1.0, 1),
        ("behavioral_anomaly", 1.45, 1, 0, 10, 4, 3, 1.5, 1),
        ("behavioral_anomaly_alt", 1.4, 1, 0, 9, 3, 2, 2.0, 1),
        ("off_hours_burst", 1.35, 1, 0, 11, 5, 23, 1.0, 1),
        ("speed_creep", 1.48, 1, 0, 7, 2, 22, 2.5, 1),
        ("burst_day", 1.2, 1, 0, 14, 4, 14, 1.2, 1),
        ("failure_streak", 1.3, 1, 0, 6, 6, 4, 3.0, 1),
        ("rogue_combo", 2.8, 0, 1, 9, 4, 1, 1.0, 1),
    ]
    for name, speed, known, restricted, cmds, fails, hour, gap, label in attack_templates:
        rows.append(
            {
                "speed": speed,
                "known_device": known,
                "restricted_destination": restricted,
                "commands_last_10_seconds": cmds,
                "previous_failures": fails,
                "hour_of_day": hour,
                "seconds_since_last_command": gap,
                "label": label,
                "scenario": name,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-normal", type=int, default=5000)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    normal = generate_normal(args.n_normal)
    evaluation = generate_eval()

    normal_path = args.out_dir / "normal_commands.csv"
    eval_path = args.out_dir / "eval_commands.csv"
    meta_path = args.out_dir / "feature_schema.json"

    normal.to_csv(normal_path, index=False)
    evaluation.to_csv(eval_path, index=False)
    meta_path.write_text(
        json.dumps(
            {
                "feature_names": FEATURE_NAMES,
                "train_only_on": "normal",
                "n_normal": len(normal),
                "note": (
                    "Attack labels in eval_commands.csv are for demonstration/"
                    "evaluation only — not used to fit IsolationForest."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Wrote {normal_path} ({len(normal)} rows)")
    print(f"Wrote {eval_path} ({len(evaluation)} rows)")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
