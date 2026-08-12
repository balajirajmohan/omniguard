import os

JWT_SECRET = os.getenv("OMNIGUARD_JWT_SECRET", "omniguard-hackathon-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
BROKER_HOST = os.getenv("OMNIGUARD_HOST", "0.0.0.0")
BROKER_PORT = int(os.getenv("OMNIGUARD_PORT", "8000"))

# Known zone coordinates (meters) for the digital twin MVP
ZONES = {
    "ZONE_A": {"x": 0.0, "y": 0.0, "label": "Staging aisle"},
    "ZONE_B": {"x": 12.0, "y": 0.0, "label": "Pick face B"},
    "HUMAN_ZONE": {"x": 6.0, "y": 8.0, "label": "Pedestrian walkway"},
}

RESTRICTED_ZONES = {"HUMAN_ZONE"}

# Default legitimate fleet agent permissions
DEFAULT_AGENT = {
    "sub": "fleet-agent-01",
    "robots": ["robot-01"],
    "zones": ["ZONE_A", "ZONE_B"],
    "max_speed": 1.5,
    "device_id": "controller-01",
}
