#!/bin/bash
# ============================================================
# TRISHULA GCP e2-micro RESEARCH HOST -- BOOTSTRAP
# trishula-research-host | us-central1-a | Debian 12
# ============================================================
# Run once after VM creation:
#   gcloud compute ssh trishula-research-host --zone us-central1-a --command "bash bootstrap_gcp_micro.sh"
# Or paste directly into SSH session from GCP Console

set -e

echo "=================================================="
echo "  TRISHULA GCP RESEARCH HOST -- BOOTSTRAP"
echo "=================================================="

# Update + essential tools
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv git curl wget unzip \
    build-essential libssl-dev libffi-dev python3-dev jq

echo "[OK] System packages installed"

# Python environment
python3 -m venv /home/debian/trishula-env
source /home/debian/trishula-env/bin/activate

pip install --quiet --upgrade pip
pip install --quiet \
    requests boto3 \
    google-generativeai \
    google-cloud-language \
    google-cloud-vision \
    azure-ai-textanalytics \
    oracledb \
    oci \
    yfinance pandas numpy \
    flask gunicorn \
    discord-webhook

echo "[OK] Python packages installed"

# Create project directory
mkdir -p /home/debian/trishula
mkdir -p /home/debian/trishula/logs
mkdir -p /home/debian/trishula/oracle_wallet

echo "[OK] Directories created"

# Install Oracle instant client (for oracledb thick mode)
wget -q https://download.oracle.com/otn_software/linux/instantclient/2113000/instantclient-basiclite-linux.x64-21.13.0.0.0dbru.zip -O /tmp/ic.zip 2>/dev/null || true
if [ -f /tmp/ic.zip ]; then
    unzip -q /tmp/ic.zip -d /opt/oracle 2>/dev/null || true
    echo "export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_13:\$LD_LIBRARY_PATH" >> /home/debian/.bashrc
    echo "[OK] Oracle instant client installed"
fi

# GCP VM metadata service — pull project ID
PROJECT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google" 2>/dev/null || echo "trishula")
ZONE=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/zone" -H "Metadata-Flavor: Google" 2>/dev/null | cut -d/ -f4 || echo "us-central1-a")

echo "[INFO] Project: $PROJECT | Zone: $ZONE"

# Simple health endpoint so we can probe from Python
cat > /home/debian/trishula/health_server.py << 'EOF'
#!/usr/bin/env python3
"""Lightweight health check server — port 80"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, datetime

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps({
            "status": "TRISHULA_GCP_LIVE",
            "host": "trishula-research-host",
            "zone": "us-central1-a",
            "ts": datetime.datetime.utcnow().isoformat() + "Z"
        })
        self.wfile.write(body.encode())
    def log_message(self, *args): pass  # suppress access log

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
EOF

# Start health server as background service
cat > /etc/systemd/system/trishula-health.service << 'EOF'
[Unit]
Description=Trishula GCP Health Server
After=network.target

[Service]
Type=simple
User=debian
WorkingDirectory=/home/debian/trishula
ExecStart=/home/debian/trishula-env/bin/python3 /home/debian/trishula/health_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable trishula-health
sudo systemctl start trishula-health

echo ""
echo "=================================================="
echo "  TRISHULA GCP RESEARCH HOST -- READY"
echo "=================================================="
echo "  Health endpoint: http://$(curl -s ifconfig.me 2>/dev/null || echo '<external-ip>'):8080"
echo "  Python env:      /home/debian/trishula-env"
echo "  Project dir:     /home/debian/trishula"
echo ""
echo "  All packages: requests, boto3, google-ai, azure, oracledb, oci, yfinance"
echo "=================================================="
