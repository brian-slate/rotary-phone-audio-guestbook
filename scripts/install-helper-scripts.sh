#!/bin/bash
# Install helper scripts to user home directory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="$HOME"

echo "Installing helper scripts to $HOME_DIR..."

# Copy add-wifi to home directory
if [ -f "$SCRIPT_DIR/add-wifi" ]; then
    cp "$SCRIPT_DIR/add-wifi" "$HOME_DIR/"
    chmod +x "$HOME_DIR/add-wifi"
    echo "✓ Installed add-wifi to $HOME_DIR/add-wifi"
else
    echo "✗ add-wifi script not found"
fi

echo "Done!"
