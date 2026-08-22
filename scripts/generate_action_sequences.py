#!/usr/bin/env python3
"""Generate synthetic normal/abnormal action-window feature rows."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts"

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


def main() -> None:
    rng = np.random.default_rng(21)
    n = 4000
    arm = rng.choice([0, 0, 0, 0, 1], n)
    # Normal windows never combine arm + gripper bursts.
    gripper = np.where(arm > 0, 0, rng.choice([0, 0, 0, 0, 1], n))
    switches = rng.integers(0, 3, n)
    normal = np.column_stack(
        [
            rng.integers(2, 35, n),
            arm,
            gripper,
            switches,
            rng.uniform(0.4, 1.1, n),
            rng.uniform(0.35, 0.95, n),
            rng.integers(0, 2, n),
            np.minimum(gripper, 1),
            np.zeros(n),
            np.zeros(n),
            np.zeros(n),
            rng.integers(8, 18, n),
            rng.uniform(0.2, 12.0, n),
        ]
    )

    # Abnormal: valid identity manipulation burst (arm + gripper + rapid switches).
    abnormal = np.array(
        [
            [4, 3, 3, 8, 0.8, 0.7, 1, 3, 1, 1, 0, 14, 0.2],
            [5, 4, 4, 10, 0.9, 0.8, 1, 4, 1, 1, 0, 15, 0.15],
            [3, 4, 4, 9, 0.7, 0.65, 0, 4, 1, 1, 1, 3, 0.1],
            [6, 5, 5, 12, 1.1, 0.9, 2, 5, 1, 1, 0, 22, 0.08],
            [2, 3, 3, 7, 0.8, 0.7, 0, 3, 1, 1, 0, 2, 0.12],
            [4, 4, 3, 9, 0.85, 0.78, 1, 3, 1, 1, 0, 23, 0.1],
            [5, 3, 4, 11, 1.0, 0.85, 1, 4, 1, 1, 2, 1, 0.05],
            [3, 3, 3, 8, 0.8, 0.72, 0, 3, 1, 1, 0, 4, 0.18],
        ],
        dtype=float,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    normal_path = OUT / "action_window_normal.csv"
    eval_path = OUT / "action_window_eval.csv"
    with normal_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(FEATURE_NAMES)
        writer.writerows(normal.tolist())

    with eval_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["label", *FEATURE_NAMES, "scenario"])
        for i, row in enumerate(normal[:40]):
            writer.writerow([0, *row.tolist(), f"eval_normal_{i}"])
        for i, row in enumerate(abnormal):
            writer.writerow([1, *row.tolist(), f"malicious_manip_{i}"])

    print(f"wrote {normal_path} ({n} rows)")
    print(f"wrote {eval_path}")


if __name__ == "__main__":
    main()
