#!/bin/bash
# Runs once at first boot (cloud-init). Installs the NVIDIA driver and
# prepares (but does not run) the Isaac Sim install, since that's a
# multi-GB download best watched interactively rather than run unattended.
set -euxo pipefail
exec > /var/log/omniguard-bootstrap.log 2>&1

apt-get update
apt-get install -y ubuntu-drivers-common build-essential python3 python3-venv git

ubuntu-drivers autoinstall

# Isaac Sim's pip package name/version/index may shift between releases —
# check NVIDIA's current Isaac Sim install docs before relying on this as-is.
cat > /home/ubuntu/install_isaac_sim.sh <<'EOF'
#!/bin/bash
set -euxo pipefail
python3 -m venv ~/isaac-sim-venv
source ~/isaac-sim-venv/bin/activate
pip install --upgrade pip
pip install "isaacsim[all]==6.0.0" --extra-index-url https://pypi.nvidia.com
echo "Installed into ~/isaac-sim-venv. Activate it, then run warehouse_robot_demo.py."
EOF
chmod +x /home/ubuntu/install_isaac_sim.sh
chown ubuntu:ubuntu /home/ubuntu/install_isaac_sim.sh

touch /home/ubuntu/BOOTSTRAP_DONE
chown ubuntu:ubuntu /home/ubuntu/BOOTSTRAP_DONE

# Reboot so the freshly installed NVIDIA driver's kernel module loads.
reboot
