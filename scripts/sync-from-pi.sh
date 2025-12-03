#!/bin/bash
# Sync project files from Pi to local Mac
# Run this from your Mac in the project root directory

PI_USER="admin"
PI_HOST="blackbox.local"
PI_PROJECT_DIR="/home/admin/rotary-phone-audio-guestbook"

echo "Syncing from Pi to local Mac..."

rsync -avz --progress \
  --exclude 'recordings/' \
  --exclude '*.pyc' \
  --exclude '__pycache__/' \
  --exclude '.git/' \
  --exclude 'venv/' \
  --exclude '*.backup' \
  --exclude '*.gpiozero-backup' \
  "${PI_USER}@${PI_HOST}:${PI_PROJECT_DIR}/" .

echo ""
echo "✓ Sync complete!"
echo ""
echo "Changes pulled:"
echo "  - Updated src/audioGuestBook.py (improved GPIO polling)"
echo "  - Updated config.yaml"
echo "  - New scripts/ folder with helper scripts"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Commit: git add . && git commit -m 'Improved GPIO button detection'"
echo "  3. Push to your fork"
