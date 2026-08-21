# Cloud GPU setup for Isaac Sim

Do this first — before any OmniGuard work — since it's the plan's biggest
dependency risk. This dev machine is macOS/Apple Silicon, which Isaac Sim
does not support at all, so Isaac Sim must run on a separate host.

## What to provision

- OS: Ubuntu 22.04 or 24.04 (simplest for cloud GPU instances), or Windows
  11 if your provider offers a GPU-enabled Windows image.
- GPU: RTX-class with **16GB+ VRAM** minimum (L4, L40S, A10G, or better; a
  consumer RTX 4080/4090-equivalent cloud SKU also works). Isaac Sim's
  minimum listed spec is 32GB system RAM + 16GB VRAM — treat that as a
  floor, not a target, since warehouse scenes with multiple robots are
  heavier.
- Storage: 100GB+ (Isaac Sim + cached USD assets add up fast).

## Picking a provider

Any of these work; pick whichever your team already has credits/access for:

- A general cloud GPU provider (AWS, GCP, Azure) with an NVIDIA RTX/L-series
  or A-series GPU instance type and the NVIDIA driver preinstalled (or
  install via the provider's GPU driver package).
- A GPU-rental service aimed at ML/graphics workloads (e.g. Lambda, Brev,
  Paperspace, RunPod) — usually faster to spin up than hyperscaler consoles
  and often cheaper per hour for a single GPU.

Whichever you pick, confirm the instance actually has an NVIDIA GPU attached
(not just a generic VM) before installing anything.

## Setup checklist

1. Launch the instance, SSH in.
2. Verify the GPU is visible: `nvidia-smi` — confirm driver version and that
   the GPU shows up with 16GB+ VRAM.
3. Install Isaac Sim. Two paths:
   - **Omniverse Launcher / desktop install** — needs a GUI or remote
     desktop/VNC session on the instance, plus a way to view the render
     (X11 forwarding is usually too slow; use NoMachine/VNC or the
     instance provider's remote-desktop feature instead).
   - **`pip install isaacsim[all]`** into a Python 3.10/3.11 venv — the
     more recent, container-friendly install path, better suited to a
     headless cloud box. Run scripts with `isaacsim.exp.full.kit` or via
     `python.sh` depending on how the package lays things out for your
     Isaac Sim version; check the version-specific docs after installing,
     since exact entry points shift between releases.
4. Confirm the Milestone 0 checkpoint from [../isaac/README.md](../isaac/README.md):
   Isaac Sim launches, a bundled warehouse opens, one bundled robot moves
   via an NVIDIA example script — before touching anything in this repo.
5. Open port 8899 (OmniGuard's Isaac bridge) in the instance's
   firewall/security group, restricted to the IP of whichever machine runs
   the OmniGuard broker. Don't expose it to 0.0.0.0/0 — the bridge itself
   has no auth, by design, since OmniGuard's policy checks already
   happened upstream.
6. Note the instance's public/reachable IP — you'll set
   `ISAAC_BRIDGE_URL=http://<that-ip>:8899` on the broker side later
   (see [../isaac/README.md](../isaac/README.md)).

## If you're demoing live at the hackathon venue

Confirm venue wifi/network can reach the cloud instance's IP and port 8899
before you're on stage — venue networks sometimes block non-standard
outbound ports. If in doubt, tunnel through something known-open (e.g. an
SSH tunnel or a reverse proxy on port 443) as a fallback, and record the
backup video (see the plan's hours 19–22) in case the network fails live.
