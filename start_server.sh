#!/bin/bash
source /home/admin/rotary-phone-audio-guestbook/.venv/bin/activate

# Set PYTHONPATH to include webserver directory for imports
export PYTHONPATH=/home/admin/rotary-phone-audio-guestbook/webserver:$PYTHONPATH

# Bind to all interfaces so it works on any IP (WiFi, ethernet, localhost)
exec gunicorn -w 1 -k gevent -b 0.0.0.0:8080 webserver.server:app
