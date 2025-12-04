#!/bin/bash
# Shared script to merge config.yaml on remote Pi
# Usage: Called via SSH from deploy.sh or sync-to-pi.sh

PROJECT_DIR="${1:-/home/admin/rotary-phone-audio-guestbook}"

cd "${PROJECT_DIR}" || exit 1

if [ -f "config.yaml.template" ] && [ -f "config.yaml" ]; then
    echo "Merging config.yaml (preserving your settings)..."
    python3 scripts/merge_config.py \
        config.yaml.template \
        config.yaml \
        config.yaml.merged
    
    if [ $? -eq 0 ]; then
        mv config.yaml.merged config.yaml
        echo "Config merge completed successfully"
    else
        echo "Warning: Config merge failed, keeping existing config"
        exit 1
    fi
else
    echo "No config template found, skipping merge"
fi
