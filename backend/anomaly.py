"""Small behavioural anomaly detector for the hackathon demo."""

from __future__ import annotations

import math

import numpy as np
from sklearn.ensemble import IsolationForest


FEATURE_NAMES = [
    "speed",
    "known_device",
    "restricted_destination",
    "commands_last_10_seconds",
    "previous_failures",
]


class CommandAnomalyDetector:
    def __init__(self) -> None:
        rng = np.random.default_rng(42)
        normal = np.column_stack(
            [
                rng.uniform(0.3, 1.2, 600),
                np.ones(600),
                np.zeros(600),
                rng.integers(0, 4, 600),
                rng.integers(0, 2, 600),
            ]
        )
        self.model = IsolationForest(
            n_estimators=150,
            contamination=0.03,
            random_state=42,
        )
        self.model.fit(normal)

    def score(
        self,
        *,
        speed: float,
        known_device: bool,
        restricted_destination: bool,
        commands_last_10_seconds: int,
        previous_failures: int,
    ) -> tuple[float, dict[str, float]]:
        values = np.array(
            [
                speed,
                float(known_device),
                float(restricted_destination),
                commands_last_10_seconds,
                previous_failures,
            ],
            dtype=float,
        )
        raw = float(self.model.decision_function(values.reshape(1, -1))[0])
        # IsolationForest: lower/negative = more anomalous. Map to 0..1 risk.
        risk = 1.0 / (1.0 + math.exp(25.0 * (raw - 0.05)))
        risk = round(max(0.01, min(0.99, risk)), 2)
        features = dict(zip(FEATURE_NAMES, values.tolist(), strict=True))
        return risk, features


detector = CommandAnomalyDetector()
