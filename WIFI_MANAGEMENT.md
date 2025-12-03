# WiFi Management via Web UI

## Overview

BLACK BOX now supports managing WiFi networks directly from the web interface. This makes it easy to add venue WiFi networks on-site without needing SSH access.

## Features

- **Current Connection Status**: See which network you're connected to, IP address, and signal strength
- **Scan for Networks**: Discover available WiFi networks with signal strength indicators
- **Add Networks**: Save new WiFi credentials with priority settings
- **Manage Saved Networks**: View and delete saved networks
- **Priority-Based Connection**: Higher priority networks are automatically preferred

## Usage Workflow

### On-Site Setup (Recommended)

1. **Connect to your mobile hotspot** (which should already be saved with high priority)
2. **Open web UI**: Navigate to `http://blackbox.local:8080/config`
3. **Scan for venue WiFi**: Click the "Scan" button in the WiFi Networks section
4. **Add venue network**:
   - Click on the network name (or manually enter SSID)
   - Enter the password
   - Set priority (e.g., 4 for venue, 10 for your hotspot)
   - Click "Add Network"
5. **Wait for connection**: The Pi will automatically connect to the venue network
6. **Turn off hotspot**: Once connected to venue WiFi, disable your mobile hotspot

### At Home Setup

You can pre-configure networks before going to an event:

```bash
# SSH into the Pi
ssh admin@blackbox

# Run the add-wifi script
~/rotary-phone-audio-guestbook/scripts/add-wifi
```

Or use the web UI at home if already connected to your home network.

## Priority Guidelines

- **Mobile Hotspot**: Priority 10 (highest - always available backup)
- **Venue WiFi**: Priority 4-6 (connect when available)
- **Home WiFi**: Priority 5 (medium)
- **Other networks**: Priority 1-3 (lowest)

The Pi will automatically connect to the highest priority network that's available.

## Technical Details

### Components

1. **wifi_manager.py**: Python module handling WiFi operations via `wpa_cli` and `wpa_supplicant.conf`
2. **API Endpoints**: `/api/wifi/{scan,current,saved,add,delete}` for programmatic access
3. **Web UI**: WiFi Networks card in the config page
4. **Sudo Configuration**: Passwordless sudo for specific WiFi commands

### Permissions

The deployment script automatically configures passwordless sudo for:
- `wpa_cli` - WiFi scanning and reconfiguration
- Reading/writing `/etc/wpa_supplicant/wpa_supplicant.conf`

This is configured in `/etc/sudoers.d/wifi-manager` on the Pi.

### Security Considerations

- **Local network only**: The web UI has no authentication and should only be accessible on trusted networks
- **Plain text passwords**: WiFi passwords are stored encrypted as PSK in `wpa_supplicant.conf`
- **Sudo access**: Limited to specific WiFi management commands only

## Deployment

### First-Time Setup

Run the full deploy script which will configure everything:

```bash
./deploy.sh blackbox
```

This will:
1. Sync all files including `wifi_manager.py`
2. Configure passwordless sudo for WiFi commands
3. Restart services

### Manual Sudo Configuration

If you need to manually configure sudo permissions:

```bash
ssh admin@blackbox
cd ~/rotary-phone-audio-guestbook
bash scripts/configure-wifi-sudo.sh
```

## Troubleshooting

### "Scan failed" error

**Cause**: `wpa_cli` doesn't have sudo permissions

**Fix**: Run the sudo configuration script:
```bash
ssh admin@blackbox "bash ~/rotary-phone-audio-guestbook/scripts/configure-wifi-sudo.sh"
```

### "Failed to add network" error

**Cause**: Invalid password or SSID, or permissions issue

**Fix**: 
1. Verify the password is correct
2. Check sudo permissions are configured
3. Check logs: `ssh admin@blackbox "sudo journalctl -u audioGuestBookWebServer.service -n 50"`

### Network doesn't connect after adding

**Cause**: Priority conflict or incorrect password

**Fix**:
1. Delete and re-add the network with correct password
2. Check saved networks list to verify priority
3. Try manual connection: `ssh admin@blackbox "sudo wpa_cli -i wlan0 reconfigure"`

### Can't access web UI after changing networks

**Cause**: Pi switched to new network but you're still on old network

**Fix**: Connect your device to the same network as the Pi

## API Reference

### GET /api/wifi/scan
Scan for available networks.

**Response:**
```json
{
  "success": true,
  "networks": [
    {
      "ssid": "VenueWiFi",
      "signal": "85",
      "frequency": "2437",
      "encryption": "WPA2/WPA3"
    }
  ]
}
```

### GET /api/wifi/current
Get currently connected network.

**Response:**
```json
{
  "success": true,
  "network": {
    "ssid": "MyPhone",
    "ip_address": "192.168.1.50/24",
    "signal": "92"
  }
}
```

### GET /api/wifi/saved
List saved networks.

**Response:**
```json
{
  "success": true,
  "networks": [
    {
      "ssid": "MyPhone",
      "priority": 10
    }
  ]
}
```

### POST /api/wifi/add
Add a new network.

**Request:**
```json
{
  "ssid": "VenueWiFi",
  "password": "secretpass",
  "priority": 4
}
```

**Response:**
```json
{
  "success": true,
  "message": "Network 'VenueWiFi' added successfully"
}
```

### POST /api/wifi/delete
Delete a saved network.

**Request:**
```json
{
  "ssid": "OldNetwork"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Network 'OldNetwork' deleted successfully"
}
```

## Future Enhancements

Potential improvements for future versions:

- **Captive Portal Mode**: Automatic AP mode when no networks available (more complex, see WARP.md for analysis)
- **Connection Testing**: Verify internet connectivity after connecting
- **Password Visibility Toggle**: Show/hide password in the form
- **Network Strength History**: Track signal strength over time
- **Auto-reconnect**: Automatic reconnection after network issues
- **QR Code Support**: Generate QR codes for easy mobile access to config page

## Files Modified

- `webserver/wifi_manager.py` (new)
- `webserver/server.py` (added WiFi endpoints)
- `webserver/templates/config.html` (added WiFi UI)
- `scripts/configure-wifi-sudo.sh` (new)
- `deploy.sh` (added WiFi sudo configuration step)
