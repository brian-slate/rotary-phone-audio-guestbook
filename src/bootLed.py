#!/usr/bin/env python3
"""
Boot LED Animation - Shows amber breathing LED while system is booting.
Runs as a systemd service that starts early and stops when audioGuestBook starts.
"""

import time
import signal
import sys
import math

try:
    import board
    import neopixel
    LED_AVAILABLE = True
except ImportError:
    LED_AVAILABLE = False
    print("NeoPixel library not available")
    sys.exit(0)

# LED Configuration
LED_COUNT = 13
LED_PIN = board.D18
LED_STATUS_INDEX = 6  # 7th LED (0-indexed)
MAX_BRIGHTNESS = 77   # 30% of 255

running = True

def signal_handler(sig, frame):
    """Handle shutdown signal gracefully."""
    global running
    running = False

def main():
    global running
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        pixels = neopixel.NeoPixel(
            LED_PIN,
            LED_COUNT,
            brightness=0.8,
            auto_write=False,
            pixel_order=neopixel.RGB
        )
    except Exception as e:
        print(f"Failed to initialize LEDs: {e}")
        sys.exit(1)
    
    print("Boot LED animation started - amber breathing on status LED")
    
    # Breathing animation parameters
    cycle_time = 2.0  # 2 seconds per full breath cycle
    step_delay = 0.03  # ~33fps
    
    start_time = time.time()
    
    while running:
        # Calculate breathing brightness using sine wave (0 to 1 to 0)
        elapsed = time.time() - start_time
        # Sine wave from 0 to 1: (sin(x) + 1) / 2
        breath = (math.sin(elapsed * math.pi / (cycle_time / 2)) + 1) / 2
        
        # Amber color at breathing brightness (0 to 30%)
        brightness = int(MAX_BRIGHTNESS * breath)
        amber_r = brightness
        amber_g = int(brightness * 0.3)  # Amber has some green (~30%)
        
        # Set only the status LED
        pixels.fill((0, 0, 0))
        pixels[LED_STATUS_INDEX] = (amber_r, amber_g, 0)
        pixels.show()
        
        time.sleep(step_delay)
    
    # Turn off LED when stopping
    pixels.fill((0, 0, 0))
    pixels.show()
    print("Boot LED animation stopped")

if __name__ == "__main__":
    main()
