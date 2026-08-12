#!/usr/bin/env python3
"""Attacker reuses a stolen valid token from a rogue controller toward HUMAN_ZONE."""

from __future__ import annotations

import argparse
import json
import sys

import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"


def main() -> int:
    parser = argparse.ArgumentParser(description="OmniGuard attack client")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--destination", default="HUMAN_ZONE")
    parser.add_argument("--speed", type=float, default=1.2)
    parser.add_argument(
        "--device-id",
        default="rogue-controller",
        help="Device ID that does not match the stolen credential",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="After first DENY, immediately reuse the same token (should also fail)",
    )
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        # Steal a technically valid fleet credential
        token_resp = client.post("/tokens/demo-agent")
        token_resp.raise_for_status()
        token_payload = token_resp.json()
        token = token_payload["access_token"]
        claims = token_payload["claims"]
        print("Stolen valid token claims:")
        print(json.dumps(claims, indent=2))

        attack = {
            "robot_id": "robot-01",
            "destination_zone": args.destination,
            "speed": args.speed,
            "device_id": args.device_id,
        }
        print("\nAttack command:")
        print(json.dumps(attack, indent=2))

        resp = client.post(
            "/commands/move",
            json=attack,
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        print("\nFirst attack decision:")
        print(json.dumps(data, indent=2, default=str))

        if data.get("decision") != "DENY" or not data.get("contained"):
            print("\nExpected DENY + containment for attack path.", file=sys.stderr)
            return 1

        print("\nCheckpoint B (attack): DENY + credential revoked / identity quarantined")

        if args.reuse:
            reuse_resp = client.post(
                "/commands/move",
                json=attack,
                headers={"Authorization": f"Bearer {token}"},
            )
            reuse_data = reuse_resp.json()
            print("\nReuse attack decision:")
            print(json.dumps(reuse_data, indent=2, default=str))
            if reuse_data.get("decision") != "DENY":
                print("\nExpected second DENY after revocation.", file=sys.stderr)
                return 1
            print("\nCheckpoint B (reuse): DENY on revoked token")

        return 0


if __name__ == "__main__":
    raise SystemExit(main())
