#!/bin/bash
#
# Configure passwordless sudo for WiFi management commands
# Run this script on the Raspberry Pi as the admin user
#

echo "Configuring passwordless sudo for WiFi management..."

# Create sudoers file for WiFi commands
sudo tee /etc/sudoers.d/wifi-manager > /dev/null <<EOF
# WiFi management commands for web UI
# Allow admin user to run WiFi commands without password
admin ALL=(ALL) NOPASSWD: /sbin/wpa_cli
admin ALL=(ALL) NOPASSWD: /bin/cat /etc/wpa_supplicant/wpa_supplicant.conf
admin ALL=(ALL) NOPASSWD: /usr/bin/tee /etc/wpa_supplicant/wpa_supplicant.conf
admin ALL=(ALL) NOPASSWD: /usr/bin/tee -a /etc/wpa_supplicant/wpa_supplicant.conf
EOF

# Set proper permissions on sudoers file
sudo chmod 0440 /etc/sudoers.d/wifi-manager

echo "✓ Passwordless sudo configured for WiFi commands"
echo ""
echo "The following commands can now run without password:"
echo "  - wpa_cli (for scanning and reconfiguring WiFi)"
echo "  - cat /etc/wpa_supplicant/wpa_supplicant.conf (for reading saved networks)"
echo "  - tee /etc/wpa_supplicant/wpa_supplicant.conf (for adding/deleting networks)"
echo ""
echo "You can now manage WiFi networks from the web UI at camphone.local:8080/config"
