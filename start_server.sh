#!/bin/bash
source /home/admin/rotary-phone-audio-guestbook/.venv/bin/activate

# Set PYTHONPATH to include webserver directory for imports
export PYTHONPATH=/home/admin/rotary-phone-audio-guestbook/webserver:$PYTHONPATH

IP_ADDRESS=$(/sbin/ip -4 addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
exec gunicorn -w 1 -k gevent -b ${IP_ADDRESS}:8080 webserver.server:app
