#!/bin/bash

# Simple sync script to upload code to Raspberry Pi
# Usage: ./sync-to-pi.sh [IP_ADDRESS]

# Raspberry Pi settings
RPI_USER="admin"
RPI_IP="${1:-192.168.xx.xx}"  # Use provided IP or default
RPI_PROJECT_DIR="/home/${RPI_USER}/rotary-phone-audio-guestbook"

echo "=== Syncing code to Raspberry Pi at ${RPI_IP} ==="

# Sync files (excluding recordings, backups, etc.)
rsync -avz --exclude-from='./rsync-exclude.txt' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'recordings/' \
    --exclude 'backup/' \
    --exclude '.DS_Store' \
    ./ ${RPI_USER}@${RPI_IP}:${RPI_PROJECT_DIR}/

if [ $? -eq 0 ]; then
    echo "=== Sync completed successfully ==="
    echo ""
    echo "Next steps:"
    echo "1. SSH into the Pi: ssh ${RPI_USER}@${RPI_IP}"
    echo "2. Restart services:"
    echo "   sudo systemctl restart audioGuestBook.service"
    echo "   sudo systemctl restart audioGuestBookWebServer.service"
    echo "3. Test at: http://${RPI_IP}:8080"
else
    echo "Error: Sync failed"
    exit 1
fi
