# Isaac Sim integration

This directory only matters once you have a Windows/Ubuntu box with an RTX
GPU (16GB+ VRAM) — see [../docs/cloud_gpu_setup.md](../docs/cloud_gpu_setup.md).
Everything else in the repo (broker, policy engine, dashboard, attack demo)
works today without it, using `OMNIGUARD_ROBOT_BACKEND=mock`.

## Milestone 0 (do this before touching OmniGuard)

Per NVIDIA's own guidance, prove the basics work before wiring in security:

1. Isaac Sim launches on the GPU host.
2. A bundled warehouse scene opens (use the Warehouse Creator extension or
   `Isaac/Environments/Simple_Warehouse/warehouse.usd` directly).
3. A bundled mobile robot (Nova Carter) moves using an NVIDIA example
   controller/script — not this repo's script yet.

Only after that milestone works, move to step 2.

## Milestone 1: wire in the OmniGuard bridge

1. Copy this `isaac/` directory to the GPU host.
2. `./python.sh warehouse_robot_demo.py` (run from Isaac Sim's install dir,
   or point `python.sh` at this script's path).
3. Confirm you see `OmniGuard Isaac bridge listening on :8899` in the
   console, and that the warehouse + Nova Carter load.
4. On the machine running the OmniGuard broker, set:
   ```
   export OMNIGUARD_ROBOT_BACKEND=isaac
   export ISAAC_BRIDGE_URL=http://<gpu-host-ip>:8899
   ```
   and restart `uvicorn broker.main:app`.
5. Open the GPU host's firewall/security group on port 8899 to the broker's
   IP only (not 0.0.0.0/0) — this bridge has no auth of its own, since
   OmniGuard's policy checks already happened before it's called.
6. Re-run `scripts/normal_client.py` — the robot should now move inside
   Isaac Sim instead of just logging in the broker's console.

## Known rough edges (untested on real hardware — see file header comments)

- Asset paths in `warehouse_robot_demo.py` match Isaac Sim 6.0's documented
  layout but occasionally shift between releases; adjust if `add_reference_to_stage`
  fails to resolve a path.
- Robot movement is kinematic (teleport-toward-target), not physics-driven
  differential drive. This is a deliberate reliability tradeoff for a
  22-hour build — swap in a real `DifferentialController` only if there's
  slack in the schedule.
