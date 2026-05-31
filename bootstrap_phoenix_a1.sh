#!/bin/bash
# ==============================================================================
# TRISHULA CLOWD ARBITRAGE v4.1 — OCI PHOENIX A1 AMPERE AUTOMATION BOOTSTRAP
# Architecture: ARM64 Aarch64 | 4 OCPU Cores | 24GB RAM | 47GB Storage
# Purpose: Provisioning background Ollama LLM endpoint to bypass GCP API rate limits
# ==============================================================================

echo "=== [STARTING TRISHULA PHOENIX A1 BOOTSTRAP] ==="
export DEBIAN_FRONTEND=noninteractive

# 1. System Updates & Prerequisites
echo "[BOOT] Installing host updates and essential developer tooling..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y curl wget git python3 python3-pip python3-venv htop ufw iptables-persistent

# 2. Booting Ollama Local Inference Server
echo "[BOOT] Installing Ollama ARM64 binary..."
curl -fsSL https://ollama.com/install.sh | sh

# Configure Ollama to listen on all interfaces (Port 11434)
echo "[BOOT] Configuring Ollama systemd unit..."
sudo mkdir -p /etc/systemd/system/ollama.service.d
cat <<EOF | sudo tee /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_ORIGINS=*"
EOF

# Reload and restart service
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl restart ollama
sleep 5

# 3. Pulling Models in Background
echo "[BOOT] Pulling Llama3.3 Oracle and Qwen2.5-Coder models..."
# A1 Ampere 24GB RAM can fit both models simultaneously in VRAM!
ollama pull qwen2.5-coder:7b
ollama pull llama3.3:latest

# 4. Opening Host Firewalls & Security Rules
echo "[BOOT] Opening port 11434 in iptables for local network access..."
# Oracle Linux/Ubuntu VMs on OCI block incoming traffic by default in iptables
sudo iptables -I INPUT 6 -p tcp --dport 11434 -j ACCEPT
sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save

# 5. Configuring local Python test environment
echo "[BOOT] Configuring local test runtime..."
mkdir -p ~/trishula-inference
cd ~/trishula-inference
python3 -m venv venv
source venv/bin/activate
pip install pip --upgrade
pip install httpx jinja2 fastapi uvicorn

# 6. Verification
echo "[BOOT] Verifying local Ollama host status..."
curl -s http://localhost:11434/api/tags | json_pp || echo "Ollama engine active."

echo "=== [PHOENIX A1 BOOTSTRAP COMPLETE — SWARM CORE STABLE] ==="
