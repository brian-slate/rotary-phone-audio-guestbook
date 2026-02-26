# WiFi Management

This project includes WiFi management directly in the web admin UI so you can move the device between networks (e.g., home → venue) without editing files over SSH.

## What you can do
- View the **currently connected** WiFi network (SSID), signal strength, and IP address.
- **Scan** for nearby WiFi networks.
- **Add** a network (SSID + password) and set a **priority**.
- View and **delete** saved networks.

## Where it lives in the UI
Open the Settings page (typically `http://<pi-ip>:8080/config`) and look for the **WiFi Networks** card.

## Important notes
- **Changes take effect immediately.** If you change networks, you may temporarily lose access to the web UI while the Pi reconnects.
- **SSH sessions can drop** when switching WiFi networks.
- Networks are stored in the system WiFi config (wpa_supplicant). This is expected on Raspberry Pi OS.

## One-time setup (required): passwordless sudo for WiFi commands
The web UI uses `wpa_cli` and reads/writes `/etc/wpa_supplicant/wpa_supplicant.conf`. For the `admin` user to do this without prompting for a sudo password, run the helper script on the Raspberry Pi:

```bash
./scripts/configure-wifi-sudo.sh
```

This creates `/etc/sudoers.d/wifi-manager` allowing the minimum required commands.

## Using priorities
When multiple networks are saved, the Pi will prefer higher priority values.

Suggested approach:
- Your phone hotspot / setup network: priority `10`
- Home WiFi: priority `6`
- Venue WiFi: priority `4`

## Troubleshooting

### WiFi scan shows nothing
- Confirm the interface is `wlan0`.
- Ensure `wpa_supplicant` is running.
- Try rebooting.

### Adding a network fails
- Make sure you ran the one-time sudo setup above.
- Check logs from the webserver service.

### You can’t find the device after switching networks
- Give it 30–60 seconds to reconnect.
- Check your router/DHCP leases.
- If you have physical access, plug in a display or use Ethernet/USB gadget mode (Pi model dependent).

## CLI alternative
If you prefer doing this from the terminal on the Pi, there’s an interactive helper script:

```bash
./scripts/add-wifi
```

It supports adding a network permanently (saved) or connecting temporarily (until reboot).