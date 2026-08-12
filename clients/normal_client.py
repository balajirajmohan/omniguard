#!/usr/bin/env python3
"""Legitimate operator: move robot-01 from ZONE_A to ZONE_B."""

from __future__ import annotations

import argparse
import json
import sys

import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    parser = argparse.ArgumentParser(description="OmniGuard normal operator client")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--destination", default="ZONE_B")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        token_resp = client.post("/tokens/demo-agent")
        token_resp.raise_for_status()
        token_payload = token_resp.json()
        token = token_payload["access_token"]
        claims = token_payload["claims"]
        print("Issued legitimate token:")
        print(json.dumps(claims, indent=2))

        move = {
            "robot_id": "robot-01",
            "destination_zone": args.destination,
            "speed": args.speed,
            "device_id": claims["device_id"],
        }
        resp = client.post(
            "/commands/move",
            json=move,
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        print("\nMove decision:")
        print(json.dumps(data, indent=2, default=str))

        if data.get("decision") != "ALLOW":
            print("\nExpected ALLOW for normal operator path.", file=sys.stderr)
            return 1
        print("\nCheckpoint B (normal): ALLOW")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
