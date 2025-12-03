"""
WiFi Manager - Utilities for managing WiFi networks on Raspberry Pi
Handles scanning, adding, removing, and listing WiFi networks using wpa_cli and wpa_supplicant.
"""

import logging
import re
import subprocess
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WiFiManager:
    """Manages WiFi operations using wpa_cli and wpa_supplicant."""
    
    WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"
    
    @staticmethod
    def scan_networks() -> List[Dict[str, str]]:
        """
        Scan for available WiFi networks.
        
        Returns:
            List of dicts with keys: ssid, signal, frequency, encryption
        """
        try:
            # Trigger scan
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "scan"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Wait a moment for scan to complete
            import time
            time.sleep(2)
            
            # Get scan results
            result = subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "scan_results"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            networks = []
            seen_ssids = set()
            
            # Parse output (skip header line)
            for line in result.stdout.strip().split('\n')[1:]:
                parts = line.split('\t')
                if len(parts) >= 5:
                    ssid = parts[4]
                    
                    # Skip hidden networks and duplicates
                    if not ssid or ssid in seen_ssids:
                        continue
                    
                    seen_ssids.add(ssid)
                    
                    networks.append({
                        'ssid': ssid,
                        'signal': WiFiManager._calculate_signal_strength(parts[2]),
                        'frequency': parts[1],
                        'encryption': WiFiManager._parse_encryption(parts[3])
                    })
            
            # Sort by signal strength (descending)
            networks.sort(key=lambda x: int(x['signal']), reverse=True)
            
            logger.info(f"Found {len(networks)} WiFi networks")
            return networks
            
        except subprocess.TimeoutExpired:
            logger.error("WiFi scan timed out")
            return []
        except subprocess.CalledProcessError as e:
            logger.error(f"WiFi scan failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during WiFi scan: {e}")
            return []
    
    @staticmethod
    def _calculate_signal_strength(rssi: str) -> str:
        """Convert RSSI to percentage (0-100)."""
        try:
            rssi_int = int(rssi)
            # RSSI typically ranges from -100 (worst) to -50 (best)
            if rssi_int <= -100:
                return "0"
            elif rssi_int >= -50:
                return "100"
            else:
                # Linear interpolation
                percentage = 2 * (rssi_int + 100)
                return str(max(0, min(100, percentage)))
        except ValueError:
            return "0"
    
    @staticmethod
    def _parse_encryption(flags: str) -> str:
        """Parse encryption type from flags."""
        if "WPA2" in flags or "WPA3" in flags:
            return "WPA2/WPA3"
        elif "WPA" in flags:
            return "WPA"
        elif "WEP" in flags:
            return "WEP"
        else:
            return "Open"
    
    @staticmethod
    def get_current_network() -> Optional[Dict[str, str]]:
        """
        Get currently connected network info.
        
        Returns:
            Dict with keys: ssid, ip_address, signal or None if not connected
        """
        try:
            # Get status
            result = subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "status"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            
            status = {}
            for line in result.stdout.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    status[key] = value
            
            if status.get('wpa_state') == 'COMPLETED':
                # Get IP address
                ip_result = subprocess.run(
                    ["ip", "-4", "addr", "show", "wlan0"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                ip_address = "Unknown"
                ip_match = re.search(r'inet\s+(\S+)', ip_result.stdout)
                if ip_match:
                    ip_address = ip_match.group(1)
                
                return {
                    'ssid': status.get('ssid', 'Unknown'),
                    'ip_address': ip_address,
                    'signal': WiFiManager._calculate_signal_strength(status.get('rssi', '-100'))
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current network: {e}")
            return None
    
    @staticmethod
    def get_saved_networks() -> List[Dict[str, any]]:
        """
        Get list of saved networks from wpa_supplicant.conf.
        
        Returns:
            List of dicts with keys: ssid, priority, network_id
        """
        try:
            result = subprocess.run(
                ["sudo", "cat", WiFiManager.WPA_SUPPLICANT_CONF],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            
            networks = []
            current_network = {}
            in_network_block = False
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                if line.startswith('network={'):
                    in_network_block = True
                    current_network = {'priority': 0}  # Default priority
                elif line == '}' and in_network_block:
                    if 'ssid' in current_network:
                        networks.append(current_network)
                    current_network = {}
                    in_network_block = False
                elif in_network_block:
                    if line.startswith('ssid='):
                        # Extract SSID (remove quotes)
                        ssid = line.split('=', 1)[1].strip().strip('"')
                        current_network['ssid'] = ssid
                    elif line.startswith('priority='):
                        try:
                            priority = int(line.split('=', 1)[1].strip())
                            current_network['priority'] = priority
                        except ValueError:
                            pass
            
            # Sort by priority (descending)
            networks.sort(key=lambda x: x.get('priority', 0), reverse=True)
            
            # Deduplicate: keep only highest priority for each SSID
            seen_ssids = set()
            unique_networks = []
            for network in networks:
                if network['ssid'] not in seen_ssids:
                    unique_networks.append(network)
                    seen_ssids.add(network['ssid'])
            
            logger.info(f"Found {len(unique_networks)} unique saved networks (deduplicated from {len(networks)} total)")
            return unique_networks
            
        except Exception as e:
            logger.error(f"Error reading saved networks: {e}")
            return []
    
    @staticmethod
    def add_network(ssid: str, password: str, priority: int = 4) -> Tuple[bool, str]:
        """
        Add a new WiFi network to wpa_supplicant.conf.
        
        Args:
            ssid: Network SSID
            password: Network password
            priority: Connection priority (higher = preferred)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not ssid:
            return False, "SSID cannot be empty"
        
        if not password:
            return False, "Password cannot be empty"
        
        try:
            # Generate encrypted PSK using wpa_passphrase
            passphrase_result = subprocess.run(
                ["wpa_passphrase", ssid, password],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            # Extract PSK line (avoid the commented plain-text password)
            psk_line = None
            for line in passphrase_result.stdout.split('\n'):
                if line.strip().startswith('psk=') and not line.strip().startswith('#psk='):
                    psk_line = line.strip()
                    break
            
            if not psk_line:
                return False, "Failed to generate encrypted password"
            
            # Create network block
            network_block = f'''
network={{
\tssid="{ssid}"
\t{psk_line}
\tpriority={priority}
}}
'''
            
            # Append to wpa_supplicant.conf
            append_cmd = f'echo "{network_block}" | sudo tee -a {WiFiManager.WPA_SUPPLICANT_CONF} > /dev/null'
            subprocess.run(
                ["bash", "-c", append_cmd],
                check=True,
                timeout=5
            )
            
            # Reconfigure wpa_supplicant to apply changes
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "reconfigure"],
                capture_output=True,
                check=True,
                timeout=5
            )
            
            logger.info(f"Added WiFi network: {ssid} with priority {priority}")
            return True, f"Network '{ssid}' added successfully"
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add network: {e}")
            return False, f"Failed to add network: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error adding network: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def delete_network(ssid: str) -> Tuple[bool, str]:
        """
        Delete a WiFi network from wpa_supplicant.conf.
        
        Args:
            ssid: Network SSID to delete
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not ssid:
            return False, "SSID cannot be empty"
        
        try:
            # Read current config
            result = subprocess.run(
                ["sudo", "cat", WiFiManager.WPA_SUPPLICANT_CONF],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            
            lines = result.stdout.split('\n')
            new_lines = []
            skip_network = False
            found_network = False
            in_network_block = False
            current_network_ssid = None
            
            for line in lines:
                stripped = line.strip()
                
                # Check if entering a network block
                if stripped.startswith('network={'):
                    in_network_block = True
                    skip_network = False
                    current_network_ssid = None
                
                # Check SSID line within network block
                elif in_network_block and stripped.startswith('ssid='):
                    # Extract SSID
                    current_network_ssid = stripped.split('=', 1)[1].strip().strip('"')
                    if current_network_ssid == ssid:
                        skip_network = True
                        found_network = True
                
                # Check end of network block
                elif stripped == '}' and in_network_block:
                    in_network_block = False
                    if skip_network:
                        # Skip the closing brace too
                        skip_network = False
                        continue
                    else:
                        new_lines.append(line)
                    continue
                
                # Add line if not skipping
                if not skip_network:
                    new_lines.append(line)
            
            if not found_network:
                return False, f"Network '{ssid}' not found in configuration"
            
            # Write updated config
            new_config = '\n'.join(new_lines)
            write_cmd = f'echo "{new_config}" | sudo tee {WiFiManager.WPA_SUPPLICANT_CONF} > /dev/null'
            subprocess.run(
                ["bash", "-c", write_cmd],
                check=True,
                timeout=5
            )
            
            # Reconfigure wpa_supplicant
            subprocess.run(
                ["sudo", "wpa_cli", "-i", "wlan0", "reconfigure"],
                capture_output=True,
                check=True,
                timeout=5
            )
            
            logger.info(f"Deleted WiFi network: {ssid}")
            return True, f"Network '{ssid}' deleted successfully"
            
        except Exception as e:
            logger.error(f"Error deleting network: {e}")
            return False, f"Error: {str(e)}"
