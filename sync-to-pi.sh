#!/bin/bash

# Simple sync script to upload code to Raspberry Pi
# Usage: ./sync-to-pi.sh [IP_ADDRESS]

# Raspberry Pi settings
RPI_USER="admin"
RPI_HOST="${1:-camphone}"  # Use provided hostname/IP or default to camphone
RPI_PROJECT_DIR="/home/${RPI_USER}/rotary-phone-audio-guestbook"

echo "=== Syncing code to Raspberry Pi at ${RPI_HOST} ==="

# Sync files (excluding recordings, backups, etc.)
rsync -avz --exclude-from='./rsync-exclude.txt' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'recordings/' \
    --exclude 'backup/' \
    --exclude '.DS_Store' \
    ./ ${RPI_USER}@${RPI_HOST}:${RPI_PROJECT_DIR}/

if [ $? -eq 0 ]; then
    echo "=== Sync completed successfully ==="
    
    # Merge config.yaml to preserve user settings while adding new defaults
    echo "Merging config.yaml (preserving your settings)..."
    ssh ${RPI_USER}@${RPI_HOST} <<ENDSSH
        cd ${RPI_PROJECT_DIR}
        if [ -f "config.yaml.template" ] && [ -f "config.yaml" ]; then
            python3 scripts/merge_config.py \
                config.yaml.template \
                config.yaml \
                config.yaml.merged
            
            if [ \$? -eq 0 ]; then
                mv config.yaml.merged config.yaml
                echo "Config merge completed successfully"
            else
                echo "Warning: Config merge failed, keeping existing config"
            fi
        else
            echo "No config template found, skipping merge"
        fi
ENDSSH
    
    echo ""
    echo "Next steps:"
    echo "1. SSH into the Pi: ssh ${RPI_USER}@${RPI_HOST}"
    echo "2. Restart services:"
    echo "   sudo systemctl restart audioGuestBook.service"
    echo "   sudo systemctl restart audioGuestBookWebServer.service"
    echo "3. Test at: http://${RPI_HOST}:8080"
else
    echo "Error: Sync failed"
    exit 1
fi
