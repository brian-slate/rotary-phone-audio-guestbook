#!/bin/bash

# Configuration
PI_USER="admin"
PI_IP="192.168.xx.xx"  # UPDATE THIS WITH YOUR PI'S IP ADDRESS
PI_PATH="/home/admin/rotary-phone-audio-guestbook"
MOUNT_POINT="$HOME/mnt/pi"

# Check if already mounted
if mount | grep -q "$MOUNT_POINT"; then
    echo "🔌 Unmounting Pi..."
    umount "$MOUNT_POINT"
    
    if [ $? -eq 0 ]; then
        echo "✅ Pi unmounted successfully"
        rmdir "$MOUNT_POINT" 2>/dev/null
    else
        echo "❌ Failed to unmount. Try: diskutil unmount force $MOUNT_POINT"
        exit 1
    fi
else
    echo "🚀 Mounting Pi..."
    
    # Create mount point if it doesn't exist
    mkdir -p "$MOUNT_POINT"
    
    # Mount the Pi
    sshfs "${PI_USER}@${PI_IP}:${PI_PATH}" "$MOUNT_POINT" -o follow_symlinks
    
    if [ $? -eq 0 ]; then
        echo "✅ Pi mounted at $MOUNT_POINT"
        echo "📂 Opening VS Code..."
        code "$MOUNT_POINT"
    else
        echo "❌ Failed to mount Pi"
        echo "Make sure:"
        echo "  1. You've updated PI_IP in this script"
        echo "  2. You have SSHFS installed: brew install macfuse sshfs"
        echo "  3. You can SSH to the Pi: ssh ${PI_USER}@${PI_IP}"
        rmdir "$MOUNT_POINT" 2>/dev/null
        exit 1
    fi
fi
