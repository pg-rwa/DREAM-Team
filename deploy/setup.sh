#!/usr/bin/env bash
# DREAM Team - DigitalOcean Droplet Setup Script
# Run this on a fresh Ubuntu 22.04+ droplet

set -euo pipefail

echo "=== DREAM Team - Server Setup ==="

# System packages
echo "[1/7] Installing system packages..."
apt-get update
apt-get install -y python3 python3-pip python3-venv git curl

# Node.js 22
echo "[2/7] Installing Node.js 22..."
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs

# Claude Code CLI
echo "[3/7] Installing Claude Code..."
npm install -g @anthropic-ai/claude-code

# Create service user
echo "[4/7] Creating service user..."
useradd -m -s /bin/bash dream 2>/dev/null || true

# Clone and install app
echo "[5/7] Setting up DREAM Team..."
mkdir -p /opt/dream-team
cd /opt/dream-team

if [ -d ".git" ]; then
    git pull
else
    echo "Please clone your DREAM-Team repo to /opt/dream-team"
    echo "  git clone https://github.com/pg-rwa/DREAM-Team.git /opt/dream-team"
fi

pip3 install --break-system-packages -e .
pip3 install --break-system-packages fastapi uvicorn python-multipart

# Create data directory
mkdir -p /home/dream/.dream-team/projects
chown -R dream:dream /home/dream/.dream-team

# Install systemd service
echo "[6/7] Installing systemd service..."
cp deploy/dream-team.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable dream-team

echo "[7/7] Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Set your Anthropic API key:"
echo "     echo 'Environment=ANTHROPIC_API_KEY=sk-ant-...' >> /etc/systemd/system/dream-team.service"
echo "     systemctl daemon-reload"
echo ""
echo "  2. Start the service:"
echo "     systemctl start dream-team"
echo ""
echo "  3. Get your API key:"
echo "     python3 -m dream_team.web.run --show-key"
echo ""
echo "  4. (Optional) Set up HTTPS with Caddy:"
echo "     apt install caddy"
echo "     echo 'yourdomain.com { reverse_proxy localhost:8000 }' > /etc/caddy/Caddyfile"
echo "     systemctl restart caddy"
echo ""
echo "  Access: http://your-server-ip:8000"
