#!/bin/bash
set -euo pipefail

REPO="elliottstorey/foundation"
BIN_NAME="foundation"
BIN_DIR="/usr/local/bin"
SERVICE_NAME="foundation"

URL=$(curl -s "https://api.github.com/repos/$REPO/releases/latest" | grep "browser_download_url" | cut -d '"' -f 4 | grep "/$BIN_NAME$" | head -n 1)

if [ -z "$URL" ]; then
    echo "Error: Release not found."
    exit 1
fi

curl -L -s -o "/tmp/$BIN_NAME" "$URL"
chmod +x "/tmp/$BIN_NAME"

if [ -w "$BIN_DIR" ]; then
    mv "/tmp/$BIN_NAME" "$BIN_DIR/$BIN_NAME"
else
    sudo mv "/tmp/$BIN_NAME" "$BIN_DIR/$BIN_NAME"
fi

if command -v systemctl >/dev/null; then
    cat <<EOF | sudo tee "/etc/systemd/system/$SERVICE_NAME.service" >/dev/null
[Unit]
Description=Foundation Auto-Updater
After=network.target docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=$BIN_DIR/$BIN_NAME deploy
User=root
WorkingDirectory=/root
StandardOutput=journal
StandardError=journal
EOF

    cat <<EOF | sudo tee "/etc/systemd/system/$SERVICE_NAME.timer" >/dev/null
[Unit]
Description=Run Foundation every 5 minutes

[Timer]
OnUnitActiveSec=5m
OnBootSec=1m

[Install]
WantedBy=timers.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now "$SERVICE_NAME.timer"
fi

echo "Foundation installed successfully. Try running foundation init."