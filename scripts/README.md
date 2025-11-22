# Helper Scripts

This folder contains useful scripts for managing the Rotary Phone Audio Guestbook.

## Scripts

### add-wifi
Interactive script to add WiFi networks to the Pi.

**Usage:**
```bash
./add-wifi
```

Options:
1. Add network permanently (saved to config with priority)
2. Connect temporarily (until reboot)

### install-helper-scripts.sh
Installs the helper scripts from this folder to your home directory for easy access.

**Usage:**
```bash
./scripts/install-helper-scripts.sh
```

## Button Detection Improvements

This fork includes improved button detection using direct GPIO polling instead of gpiozero callbacks:
- More reliable press/release detection
- No missed events
- Simpler configuration (no confusing hook_type settings)

The main code change is in `src/audioGuestBook.py` where the hook button monitoring now uses a dedicated polling thread with RPi.GPIO instead of gpiozero Button callbacks.
