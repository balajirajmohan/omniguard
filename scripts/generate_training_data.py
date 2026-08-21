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
    """Labeled evaluation scenarios (not used for IsolationForest fit)."""
    rows = [
        # Should look normal
        {
            "speed": 0.8,
            "known_device": 1,
            "restricted_destination": 0,
            "commands_last_10_seconds": 1,
            "previous_failures": 0,
            "hour_of_day": 10,
            "seconds_since_last_command": 40,
            "label": 0,
            "scenario": "eval_normal",
        },
        # Known compromise (rules would also catch)
        {
            "speed": 3.5,
            "known_device": 0,
            "restricted_destination": 1,
            "commands_last_10_seconds": 8,
            "previous_failures": 3,
            "hour_of_day": 2,
            "seconds_since_last_command": 1,
            "label": 1,
            "scenario": "known_compromise",
        },
        # Unknown / zero-day behavior: all hard rules pass
        {
            "speed": 1.45,
            "known_device": 1,
            "restricted_destination": 0,
            "commands_last_10_seconds": 10,
            "previous_failures": 4,
            "hour_of_day": 3,
            "seconds_since_last_command": 1.5,
            "label": 1,
            "scenario": "behavioral_anomaly",
        },
        {
            "speed": 1.4,
            "known_device": 1,
            "restricted_destination": 0,
            "commands_last_10_seconds": 9,
            "previous_failures": 3,
            "hour_of_day": 2,
            "seconds_since_last_command": 2.0,
            "label": 1,
            "scenario": "behavioral_anomaly_alt",
        },
        {
            "speed": 1.35,
            "known_device": 1,
            "restricted_destination": 0,
            "commands_last_10_seconds": 11,
            "previous_failures": 5,
            "hour_of_day": 23,
            "seconds_since_last_command": 1.0,
            "label": 1,
            "scenario": "off_hours_burst",
        },
    ]
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
