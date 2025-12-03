#! /usr/bin/env python3

import logging
import os
import sys
import threading
import random
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from signal import pause

import yaml
import RPi.GPIO as GPIO
from gpiozero import Button

try:
    import board
    import neopixel
    LED_AVAILABLE = True
except ImportError:
    LED_AVAILABLE = False

from audioInterface import AudioInterface

# Import AI processing components (lazy import to avoid errors if not installed)
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "webserver"))
    from job_queue import ProcessingQueue
    from openai_processor import AudioProcessor
    from metadata_manager import MetadataManager
    from connectivity_checker import ConnectivityChecker
    AI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AI processing components not available: {e}")
    AI_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CurrentEvent(Enum):
    NONE = 0
    HOOK = 1
    RECORD_GREETING = 2
    RECORD_GREETING_VIA_HOOK = 3


class AudioGuestBook:
    """
    Manages the rotary phone audio guest book application.

    This class initializes the application, handles phone hook events, and
    coordinates audio playback and recording based on the phone's hook status.

    Attributes:
        config_path (str): Path to the application configuration file.
        config (dict): Configuration parameters loaded from the YAML file.
        audio_interface (AudioInterface): Interface for audio playback and recording.
    """

    # LED Configuration
    LED_COUNT = 13           # Number of LEDs in the strip
    LED_PIN = board.D18 if LED_AVAILABLE else None  # GPIO 18 (PWM)
    LED_BRIGHTNESS = 0.8     # Default brightness (0.0 to 1.0)
    LED_STATUS_INDEX = 6     # 7th LED (0-indexed) for status indicator
    LED_AI_INDICATOR_INDEX = 4  # 5th LED (0-indexed) for AI processing indicator

    def __init__(self, config_path):
        """
        Initializes the audio guest book application with specified configuration.

        Args:
            config_path (str): Path to the configuration YAML file.
        """
        self.config_path = config_path
        self.config = self.load_config()

        # Check if the recordings folder exists, if not, create it.
        recordings_path = Path(self.config["recordings_path"])
        if not recordings_path.exists():
            logger.info(
                f"Recordings folder does not exist. Creating folder: {recordings_path}"
            )
            recordings_path.mkdir(parents=True, exist_ok=True)

        self.audio_interface = AudioInterface(
            alsa_hw_mapping=self.config["alsa_hw_mapping"],
            format=self.config["format"],
            file_type=self.config["file_type"],
            recording_limit=self.config["recording_limit"],
            sample_rate=self.config["sample_rate"],
            channels=self.config["channels"],
            mixer_control_name=self.config["mixer_control_name"],
            minimum_message_duration=self.config.get("minimum_message_duration", 2.0),
            minimum_file_size_bytes=self.config.get("minimum_file_size_bytes", 88200),
            delete_invalid_recordings=self.config.get("delete_invalid_recordings", True),
        )

        # Initialize LEDs
        self.setup_leds()

        self.setup_hook()
        self.setup_record_greeting()
        self.setup_shutdown_button()
        self.current_event = CurrentEvent.NONE
        
        # LED animation control
        self.led_animation_running = False
        self.led_animation_thread = None
        
        # AI processing indicator control
        self.ai_indicator_running = False
        self.ai_indicator_thread = None
        
        # Hook toggle tracking for record greeting mode
        self.hook_toggle_times = []
        self.pending_greeting_record = False
        self.greeting_recording_file = None
        self.greeting_recording_started = False  # Track if recording actually started
        
        # Initialize AI components if available
        self.setup_ai_processing()

    def setup_ai_processing(self):
        """Initialize AI processing components."""
        if not AI_AVAILABLE:
            logger.info("AI processing components not available, skipping AI setup")
            return
        
        try:
            # Initialize AI components
            self.metadata_manager = MetadataManager(self.config['recordings_path'])
            self.connectivity_checker = ConnectivityChecker()
            self.audio_processor = AudioProcessor(self.config)
            
            # Create phone state checker function
            def is_phone_active():
                return self.current_event != CurrentEvent.NONE
            
            # Initialize processing queue with idle-time check
            self.processing_queue = ProcessingQueue(
                self.audio_processor,
                self.metadata_manager,
                self.connectivity_checker,
                is_phone_active,
                self.config
            )
            # Register callback for AI processing state changes
            self.processing_queue.processing_callback = self.on_ai_processing_state_changed
            self.processing_queue.start()
            logger.info("AI processing queue initialized and started")
        except Exception as e:
            logger.error(f"Failed to initialize AI processing: {e}")
    
    def load_config(self):
        """
        Loads the application configuration from a YAML file.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
        """
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError as e:
            logger.error(f"Configuration file not found: {e}")
            sys.exit(1)

    def setup_leds(self):
        """
        Initialize the WS2811 LED strip and run startup animation.
        """
        if not LED_AVAILABLE:
            logger.warning("NeoPixel library not available. LED features disabled.")
            self.pixels = None
            return
        
        try:
            self.pixels = neopixel.NeoPixel(
                self.LED_PIN,
                self.LED_COUNT,
                brightness=self.LED_BRIGHTNESS,
                auto_write=False,
                pixel_order=neopixel.RGB
            )
            logger.info(f"Initialized {self.LED_COUNT} LEDs on GPIO 18")
            
            # Stop any booting animation and run startup animation
            self.led_startup_animation()
            
        except Exception as e:
            logger.error(f"Failed to initialize LEDs: {e}")
            self.pixels = None
    
    def led_startup_animation(self):
        """
        Startup: just show ready state LED (no animation).
        The boot LED service shows amber breathing during boot.
        """
        if self.pixels is None:
            return
        
        logger.info("BLACK BOX ready - showing ready state LED")
        
        # Clear any boot animation and go straight to ready state
        self.pixels.fill((0, 0, 0))
        self.pixels.show()
        time.sleep(0.1)
        
        # Show ready state
        self.led_show_ready_state()
        logger.info("LED ready state active.")
    
    def led_show_ready_state(self):
        """
        Show the ready state: single green LED (7th LED) at 30% brightness.
        """
        if self.pixels is None:
            return
        
        self.pixels.fill((0, 0, 0))  # Turn off all LEDs first
        # 30% brightness green on status LED
        self.pixels[self.LED_STATUS_INDEX] = (0, 77, 0)
        self.pixels.show()
    
    def led_start_greeting_animation(self):
        """
        Start the greeting animation: all LEDs randomly pulsing in amber/red.
        Used while greeting is playing. Runs in a separate thread.
        """
        if self.pixels is None:
            return
        
        self.led_animation_running = True
        self.led_animation_mode = "greeting"  # amber/red mix
        self.led_animation_thread = threading.Thread(target=self._led_animation_loop, daemon=True)
        self.led_animation_thread.start()
        logger.info("Started LED greeting animation")
    
    def led_switch_to_recording_mode(self):
        """
        Switch animation to recording mode: all red LEDs.
        Called when beep plays and recording starts.
        """
        if self.pixels is None:
            return
        
        self.led_animation_mode = "recording"  # all red
        logger.info("Switched LED animation to recording mode (all red)")
    
    def led_start_record_greeting_animation(self):
        """
        Start the record greeting animation: pulsing blue LED.
        Used while recording a new greeting via hook toggles.
        """
        if self.pixels is None:
            return
        
        self.led_animation_running = True
        self.led_animation_mode = "record_greeting"  # blue pulse
        self.led_animation_thread = threading.Thread(target=self._led_animation_loop, daemon=True)
        self.led_animation_thread.start()
        logger.info("Started LED record greeting animation (blue pulse)")
    
    def _led_animation_loop(self):
        """
        Animation loop: randomly pulse LEDs at 80% max brightness like old-timey computer.
        Mode "greeting": amber/red tones
        Mode "recording": all red tones
        Mode "record_greeting": pulsing blue (all LEDs synchronized)
        """
        if self.pixels is None:
            return
        
        # Initialize random brightness targets for each LED
        targets = [random.randint(50, 255) for _ in range(self.LED_COUNT)]
        current = [0] * self.LED_COUNT
        speeds = [random.randint(5, 20) for _ in range(self.LED_COUNT)]
        
        # Greeting colors (amber and red mix)
        greeting_colors = [
            (255, 80, 0),    # Amber (more red/orange)
            (255, 50, 0),    # Deep amber
            (255, 100, 20),  # Warm amber
            (255, 30, 0),    # Red-orange
            (200, 20, 0),    # Deep red
            (255, 60, 60),   # Soft red
        ]
        
        # Recording colors (all red tones)
        recording_colors = [
            (255, 0, 0),     # Pure red
            (200, 0, 0),     # Dark red
            (255, 20, 20),   # Bright red
            (180, 0, 0),     # Deep red
            (255, 40, 40),   # Soft red
            (220, 10, 10),   # Medium red
        ]
        
        led_colors = [random.choice(greeting_colors) for _ in range(self.LED_COUNT)]
        current_mode = "greeting"
        
        # For blue pulsing mode (synchronized)
        blue_pulse_direction = 1  # 1 for increasing, -1 for decreasing
        blue_pulse_value = 0
        
        while self.led_animation_running:
            # Check if mode changed and update colors
            if hasattr(self, 'led_animation_mode') and self.led_animation_mode != current_mode:
                current_mode = self.led_animation_mode
                if current_mode in ["greeting", "recording"]:
                    colors = recording_colors if current_mode == "recording" else greeting_colors
                    led_colors = [random.choice(colors) for _ in range(self.LED_COUNT)]
            
            # Handle blue pulsing mode (synchronized all LEDs)
            if current_mode == "record_greeting":
                # Smooth pulsing between 30-255
                blue_pulse_value += blue_pulse_direction * 8
                if blue_pulse_value >= 255:
                    blue_pulse_value = 255
                    blue_pulse_direction = -1
                elif blue_pulse_value <= 30:
                    blue_pulse_value = 30
                    blue_pulse_direction = 1
                
                brightness_factor = (blue_pulse_value / 255) * 0.8
                b = int(255 * brightness_factor)
                self.pixels.fill((0, 0, b))
                self.pixels.show()
                time.sleep(0.03)
                continue
            
            colors = recording_colors if current_mode == "recording" else greeting_colors
            
            for i in range(self.LED_COUNT):
                # Move current brightness toward target
                if current[i] < targets[i]:
                    current[i] = min(current[i] + speeds[i], targets[i])
                else:
                    current[i] = max(current[i] - speeds[i], targets[i])
                
                # If reached target, pick a new random target
                if current[i] == targets[i]:
                    targets[i] = random.randint(30, 255)
                    speeds[i] = random.randint(5, 25)
                    # Occasionally change color
                    if random.random() < 0.1:
                        led_colors[i] = random.choice(colors)
                
                # Apply brightness (scale by 0.8 for 80% max brightness)
                brightness_factor = (current[i] / 255) * 0.8
                r = int(led_colors[i][0] * brightness_factor)
                g = int(led_colors[i][1] * brightness_factor)
                b = int(led_colors[i][2] * brightness_factor)
                self.pixels[i] = (r, g, b)
            
            self.pixels.show()
            time.sleep(0.03)  # ~33fps animation
    
    def led_stop_animation(self):
        """
        Stop the recording animation, show saved animation, then return to ready state.
        """
        if self.pixels is None:
            return
        
        self.led_animation_running = False
        
        if self.led_animation_thread is not None:
            self.led_animation_thread.join(timeout=1.0)
            self.led_animation_thread = None
        
        # Show "saved" animation
        self.led_saved_animation()
        
        # Return to ready state
        self.led_show_ready_state()
        logger.info("Stopped LED animation, returned to ready state")

    def led_stop_animation_without_saved(self):
        """
        Stop the recording animation and go straight to ready state (no Saved flash).
        Used when the recording was discarded as junk/too short.
        """
        if self.pixels is None:
            return
        
        self.led_animation_running = False
        
        if self.led_animation_thread is not None:
            self.led_animation_thread.join(timeout=1.0)
            self.led_animation_thread = None
        
        # Directly show ready state without the green flash
        self.led_show_ready_state()
        logger.info("Stopped LED animation without Saved flash (junk/short recording)")
    
    def led_saved_animation(self):
        """
        "Saved!" animation: quick flash all LEDs to green at 100% brightness.
        Fade in quickly, hold briefly, fade out.
        """
        if self.pixels is None:
            return
        
        logger.info("Playing saved animation...")
        
        # Quick fade in to green (100% brightness)
        steps = 15
        for i in range(steps):
            brightness = i / steps
            green_value = int(255 * brightness)
            self.pixels.fill((0, green_value, 0))
            self.pixels.show()
            time.sleep(0.02)  # 20ms per step = 0.3s fade in
        
        # Hold at full green briefly
        self.pixels.fill((0, 255, 0))
        self.pixels.show()
        time.sleep(0.5)  # Hold for 0.5 seconds
        
        # Quick fade out
        for i in range(steps, -1, -1):
            brightness = i / steps
            green_value = int(255 * brightness)
            self.pixels.fill((0, green_value, 0))
            self.pixels.show()
            time.sleep(0.02)  # 20ms per step = 0.3s fade out
        
        # Turn off all LEDs
        self.pixels.fill((0, 0, 0))
        self.pixels.show()
        time.sleep(0.1)
    
    def led_cleanup(self):
        """
        Turn off all LEDs on shutdown.
        """
        if self.pixels is None:
            return
        
        self.led_animation_running = False
        self.ai_indicator_running = False
        self.pixels.fill((0, 0, 0))
        self.pixels.show()
        logger.info("LEDs turned off")
    
    def on_ai_processing_state_changed(self, is_processing: bool):
        """
        Callback invoked when AI processing starts or stops.
        Only shows indicator when phone is in ready state.
        """
        # Only show AI indicator when phone is idle (ready state)
        if self.current_event != CurrentEvent.NONE:
            return
        
        if is_processing:
            self.led_start_ai_indicator()
        else:
            self.led_stop_ai_indicator()
    
    def led_start_ai_indicator(self):
        """
        Start purple pulsing animation on LED 5 (index 4) to indicate AI processing.
        Keeps green ready LED (LED 6) lit.
        """
        if self.pixels is None:
            return
        
        if not self.ai_indicator_running:
            self.ai_indicator_running = True
            self.ai_indicator_thread = threading.Thread(
                target=self._led_ai_indicator_loop,
                daemon=True
            )
            self.ai_indicator_thread.start()
            logger.info("Started AI processing indicator (purple pulse on LED 5 / index 4)")
    
    def led_stop_ai_indicator(self):
        """
        Stop AI indicator animation and return LED 5 to off.
        Keeps green ready LED (LED 6) lit.
        """
        if self.pixels is None:
            return
        
        self.ai_indicator_running = False
        
        if self.ai_indicator_thread is not None:
            self.ai_indicator_thread.join(timeout=1.0)
            self.ai_indicator_thread = None
        
        # Turn off AI indicator LED
        self.pixels[self.LED_AI_INDICATOR_INDEX] = (0, 0, 0)
        # Keep ready LED green
        self.pixels[self.LED_STATUS_INDEX] = (0, 77, 0)
        self.pixels.show()
        logger.info("Stopped AI processing indicator")
    
    def _led_ai_indicator_loop(self):
        """
        Fast purple pulsing animation on LED 5 (index 4).
        Pulses from completely off to 30% brightness (matching ready LED level).
        """
        if self.pixels is None:
            return
        
        pulse_value = 0   # Start completely off
        direction = 1     # 1 = brightening, -1 = dimming
        max_brightness = 77  # Match the ready LED brightness (30% of 255)
        
        while self.ai_indicator_running:
            # Fast pulsing between 0-77 (off to 30% brightness, matching ready LED)
            pulse_value += direction * 3  # Adjusted for smaller range
            
            if pulse_value >= max_brightness:
                pulse_value = max_brightness
                direction = -1
            elif pulse_value <= 0:
                pulse_value = 0
                direction = 1
            
            # Purple color (more blue, some red, no green)
            brightness_factor = pulse_value / 255
            r = int(128 * brightness_factor)  # Medium red
            g = 0                              # No green
            b = int(255 * brightness_factor)  # Full blue
            
            # Update LED 5 (index 4) with purple
            self.pixels[self.LED_AI_INDICATOR_INDEX] = (r, g, b)
            # Keep LED 6 green (ready state)
            self.pixels[self.LED_STATUS_INDEX] = (0, 77, 0)
            self.pixels.show()
            
            time.sleep(0.02)  # ~50fps, faster pulse (was 0.04)

    def setup_hook(self):
        """
        Sets up GPIO button monitoring using reliable polling instead of callbacks.
        Runs in a separate thread to continuously monitor button state.
        """
        self.hook_gpio = self.config["hook_gpio"]
        self.button_pressed = False
        self.monitor_running = True
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.hook_gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        logger.info(f"Hook setup: GPIO={self.hook_gpio}, using polling mode")
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_button, daemon=True)
        self.monitor_thread.start()
        logger.info("Button monitoring thread started")
    
    def _monitor_button(self):
        """
        Continuously monitors button state in a separate thread.
        Uses two separate mechanisms:
        1. Immediate toggle counting for record mode detection (no debounce)
        2. Debounced call flow for normal pickup/hangup (prevents accidental triggers)
        """
        POLL_INTERVAL = 0.01  # 10ms polling interval
        last_state = GPIO.input(self.hook_gpio)
        last_debounced_state = last_state
        last_state_change_time = time.time()
        
        while self.monitor_running:
            current_state = GPIO.input(self.hook_gpio)
            current_time = time.time()
            
            # Detect ANY state change for toggle counting
            if current_state != last_state:
                # IMMEDIATE: Count toggles for record mode detection (no debounce)
                toggle_window = self.config.get("hook_toggle_window", 6.0)
                
                # Clean up old toggle times outside the window
                self.hook_toggle_times = [
                    t for t in self.hook_toggle_times 
                    if current_time - t < toggle_window
                ]
                
                # Add current toggle (count both directions)
                self.hook_toggle_times.append(current_time)
                
                toggle_count = len(self.hook_toggle_times)
                required_count = self.config.get("hook_toggle_count", 10)
                
                logger.info(f"Hook toggle detected: {toggle_count}/{required_count} within {toggle_window}s window (state: {current_state})")
                
                # Check if record mode threshold reached AND feature is enabled
                hook_toggle_enabled = self.config.get("hook_toggle_record_enabled", True)
                if toggle_count >= required_count and hook_toggle_enabled:
                    logger.info(f"Record greeting mode activated! ({toggle_count} toggles detected)")
                    self.pending_greeting_record = True
                    # Clear the toggle history
                    self.hook_toggle_times = []
                    
                    # If currently in a call, end it cleanly
                    if self.current_event != CurrentEvent.NONE:
                        logger.info("Ending current call to prepare for record greeting mode")
                        self.stop_recording_and_playback()
                        self.led_stop_animation()
                        self.current_event = CurrentEvent.NONE
                
                # Reset debounce timer
                last_state_change_time = current_time
                last_state = current_state
            
            # DEBOUNCED: Normal call flow (only after state settles)
            time_since_change = current_time - last_state_change_time
            debounce_time = self.config.get("hook_bounce_time", 0.2)
            
            # Only trigger call state changes after state has settled
            if time_since_change >= debounce_time and current_state != last_debounced_state:
                # State has settled, now act on it for normal call flow
                if current_state == 0:  # Button pressed (LOW - connected to ground)
                    logger.info("Hook state settled: OFF HOOK (debounced)")
                    self.off_hook()
                else:  # Button released (HIGH - pulled up)
                    logger.info("Hook state settled: ON HOOK (debounced)")
                    self.on_hook()
                
                last_debounced_state = current_state
            
            threading.Event().wait(POLL_INTERVAL)

    def off_hook(self):
        """
        Handles the off-hook event to start playback and recording.
        If pending_greeting_record is True, starts record greeting mode instead.
        """
        # Check that no other event is currently in progress
        if self.current_event != CurrentEvent.NONE:
            logger.info("Another event is in progress. Ignoring off-hook event.")
            return

        logger.info("Phone off hook, ready to begin!")

        # Ensure clean state by forcing stop of any existing processes
        self.stop_recording_and_playback()

        # Check if we should enter record greeting mode
        if self.pending_greeting_record:
            logger.info("Entering RECORD GREETING MODE via hook toggles")
            self.pending_greeting_record = False
            
            # Start blue pulsing LED animation
            self.led_start_record_greeting_animation()
            
            self.current_event = CurrentEvent.RECORD_GREETING_VIA_HOOK
            # Start the record greeting process in a separate thread
            self.greeting_thread = threading.Thread(target=self.record_greeting_via_hook)
            self.greeting_thread.start()
        else:
            # Normal call flow
            # Start LED greeting animation (amber/red mix)
            self.led_start_greeting_animation()

            self.current_event = CurrentEvent.HOOK  # Ensure playback can continue
            # Start the greeting playback in a separate thread
            self.greeting_thread = threading.Thread(target=self.play_greeting_and_beep)
            self.greeting_thread.start()

    def start_recording(self, output_file: str):
        """
        Starts the audio recording process and sets a timer for time exceeded event.
        """
        self.current_recording_path = output_file  # Store for AI processing later
        self.audio_interface.start_recording(output_file)
        logger.info("Recording started...")

        # Start a timer to handle the time exceeded event
        self.timer = threading.Timer(
            self.config["time_exceeded_length"], self.time_exceeded
        )
        self.timer.start()

    def play_greeting_and_beep(self):
        """
        Plays the greeting and beep sounds, checking for the on-hook event.
        """
        # Play the greeting
        self.audio_interface.continue_playback = self.current_event == CurrentEvent.HOOK
        logger.info("Playing voicemail...")
        self.audio_interface.play_audio(
            self.config["greeting"],
            self.config["greeting_volume"],
            self.config["greeting_start_delay"],
        )

        # Create output filename with timestamp
        timestamp = datetime.now().isoformat()
        output_file = str(
            Path(self.config["recordings_path"]) / f"{timestamp}.wav"
        )
        logger.info(f"Will save recording to: {output_file}")

        # Verify recording path exists and is writable
        recordings_path = Path(self.config["recordings_path"])
        logger.info(f"Recording directory exists: {recordings_path.exists()}")
        logger.info(f"Recording directory is writable: {os.access(str(recordings_path), os.W_OK)}")

        include_beep = bool(self.config["beep_include_in_message"])

        # Check if the phone is still off-hook
        # Start recording already BEFORE the beep (beep will be included in message)
        if self.current_event == CurrentEvent.HOOK and include_beep:
            self.start_recording(output_file)

        # Play the beep and switch to recording LED mode
        if self.current_event == CurrentEvent.HOOK:
            logger.info("Playing beep...")
            self.led_switch_to_recording_mode()  # Switch LEDs to all red
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config["beep_volume"],
                self.config["beep_start_delay"],
            )

        # Check if the phone is still off-hook
        # Start recording AFTER the beep (beep will NOT be included in message)
        if self.current_event == CurrentEvent.HOOK and not include_beep:
            self.start_recording(output_file)

    def on_hook(self):
        """
        Handles the on-hook event to stop and save the recording.
        If in record greeting mode, saves the greeting and updates config.
        """
        if self.current_event == CurrentEvent.HOOK:
            logger.info("Phone on hook. Ending call and saving recording.")
            # Stop any ongoing processes before resetting the state
            self.stop_recording_and_playback()
            
            # Decide whether to show "Saved" based on whether a valid file remains
            show_saved = False
            try:
                if hasattr(self, 'current_recording_path'):
                    file_path_tmp = Path(self.current_recording_path)
                    if file_path_tmp.exists():
                        min_size = self.audio_interface.minimum_file_size_bytes
                        size_tmp = file_path_tmp.stat().st_size
                        if size_tmp >= min_size:
                            # Optional duration check for extra safety
                            try:
                                import wave
                                with wave.open(str(file_path_tmp), 'rb') as wav:
                                    frames = wav.getnframes()
                                    rate = wav.getframerate()
                                    duration_tmp = frames / float(rate or 1)
                                if duration_tmp >= self.audio_interface.minimum_message_duration:
                                    show_saved = True
                            except Exception:
                                # If duration check fails but size is OK, still show saved
                                show_saved = True
            except Exception as _:
                show_saved = False

            # Stop LED animation and return to ready state (skip Saved if junk)
            if show_saved:
                self.led_stop_animation()
            else:
                self.led_stop_animation_without_saved()
            
            # Reset current_event BEFORE queuing AI so callback sees phone as idle
            self.current_event = CurrentEvent.NONE
            
            # Queue for AI processing if we have a recording path
            if AI_AVAILABLE and hasattr(self, 'current_recording_path') and hasattr(self, 'processing_queue'):
                file_path = Path(self.current_recording_path)
                
                if file_path.exists():
                    # Secondary pre-queue validation to avoid AI LED on junk files
                    try:
                        file_size = file_path.stat().st_size
                        min_size = self.audio_interface.minimum_file_size_bytes
                        if file_size < min_size:
                            logger.info(f"Skipping AI queue: file too small ({file_size} < {min_size} bytes): {file_path.name}")
                            file_path.unlink(missing_ok=True)
                            return
                        # Compute duration from WAV header
                        import wave
                        with wave.open(str(file_path), 'rb') as wav:
                            frames = wav.getnframes()
                            rate = wav.getframerate()
                            duration = frames / float(rate or 1)
                        min_dur = self.audio_interface.minimum_message_duration
                        if duration < min_dur:
                            logger.info(f"Skipping AI queue: duration too short ({duration:.2f}s < {min_dur:.2f}s): {file_path.name}")
                            file_path.unlink(missing_ok=True)
                            return
                    except Exception as preq_err:
                        logger.warning(f"Pre-queue validation error for {file_path.name}: {preq_err}. Skipping.")
                        try:
                            file_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                        return

                    # Initialize metadata entry
                    self.metadata_manager.initialize_recording(
                        file_path.name,
                        file_size
                    )
                    
                    # Queue for AI processing (will process when idle)
                    self.processing_queue.enqueue(
                        str(file_path),
                        file_path.name
                    )
                    logger.info(f"Queued {file_path.name} for AI processing")

            # Make sure we're ready for the next call with more verbose logging
            logger.info("=========================================")
            logger.info("System reset completed successfully")
            logger.info("Ready for next recording - lift handset to begin")
            logger.info("=========================================" )
        
        elif self.current_event == CurrentEvent.RECORD_GREETING_VIA_HOOK:
            logger.info("Phone on hook during greeting recording.")
            # Stop recording
            self.stop_recording_and_playback()
            
            # Stop LED animation
            self.led_stop_animation()
            
            # Only save if recording actually started (user didn't hang up before beep)
            if self.greeting_recording_started:
                # If recording was successful, update config
                if self.greeting_recording_file and Path(self.greeting_recording_file).exists():
                    self._save_new_greeting(self.greeting_recording_file)
                    logger.info("=========================================")
                    logger.info("New greeting saved successfully")
                    logger.info("Ready for next call - lift handset to begin")
                    logger.info("=========================================" )
                else:
                    logger.warning("Greeting recording file not found, keeping old greeting")
            else:
                logger.info("Greeting recording cancelled (hung up before recording started)")
                # Clean up the temp file if it exists
                if self.greeting_recording_file and Path(self.greeting_recording_file).exists():
                    Path(self.greeting_recording_file).unlink()
                logger.info("Keeping existing greeting. Ready for next call.")
            
            # Reset state
            self.greeting_recording_file = None
            self.greeting_recording_started = False
            self.current_event = CurrentEvent.NONE

    def time_exceeded(self):
        """
        Handles the event when the recording time exceeds the limit.
        """
        logger.info("Recording time exceeded. Stopping recording.")
        self.audio_interface.stop_recording()
        self.audio_interface.play_audio(
            self.config["time_exceeded"], self.config["time_exceeded_volume"], 0
        )

    def setup_record_greeting(self):
        """
        Sets up the phone record greeting switch with GPIO based on the configuration.
        """
        record_greeting_gpio = self.config["record_greeting_gpio"]
        if record_greeting_gpio == 0:
            logger.info("record_greeting_gpio is 0, skipping setup.")
            return
        pull_up = self.config["record_greeting_type"] == "NC"
        bounce_time = self.config["record_greeting_bounce_time"]
        self.record_greeting = Button(
            record_greeting_gpio, pull_up=pull_up, bounce_time=bounce_time
        )
        self.record_greeting.when_pressed = self.pressed_record_greeting
        self.record_greeting.when_released = self.released_record_greeting

    def shutdown(self):
        print("System shutting down...")
        os.system("sudo shutdown now")

    def setup_shutdown_button(self):
        shutdown_gpio = self.config["shutdown_gpio"]
        if shutdown_gpio == 0:
            logger.info("no shutdown button declared, skipping button init")
            return
        hold_time = self.config["shutdown_button_hold_time"] == 2
        self.shutdown_button = Button(shutdown_gpio, pull_up=True, hold_time=hold_time)
        self.shutdown_button.when_held = self.shutdown

    def pressed_record_greeting(self):
        """
        Handles the record greeting to start recording a new greeting message.
        """
        # Check that no other event is currently in progress
        if self.current_event != CurrentEvent.NONE:
            logger.info("Another event is in progress. Ignoring record greeting event.")
            return

        logger.info("Record greeting pressed, ready to begin!")

        self.current_event = (
            CurrentEvent.RECORD_GREETING
        )  # Ensure record greeting can continue
        # Start the record greeting in a separate thread
        self.greeting_thread = threading.Thread(target=self.beep_and_record_greeting)
        self.greeting_thread.start()

    def released_record_greeting(self):
        """
        Handles the record greeting event to stop and save the greeting.
        """
        # Check that the record greeting event is in progress
        if self.current_event != CurrentEvent.RECORD_GREETING:
            return

        logger.info("Record greeting released. Save the greeting.")
        self.current_event = CurrentEvent.NONE  # Stop playback and reset current event
        self.stop_recording_and_playback()

    def record_greeting_via_hook(self):
        """
        Handles recording a new greeting via hook toggles.
        Plays prompt, beep, then records until user hangs up.
        """
        self.audio_interface.continue_playback = (
            self.current_event == CurrentEvent.RECORD_GREETING_VIA_HOOK
        )
        
        # Play the record greeting prompt
        if self.current_event == CurrentEvent.RECORD_GREETING_VIA_HOOK:
            logger.info("Playing record greeting prompt...")
            self.audio_interface.play_audio(
                self.config.get("record_greeting_prompt", self.config["beep"]),
                self.config.get("greeting_volume", 1.0),
                0.5,
            )
        
        # Add a small delay BEFORE beep to let audio system settle
        # This prevents cutting off the start of the recording
        if self.current_event == CurrentEvent.RECORD_GREETING_VIA_HOOK:
            time.sleep(0.3)  # 300ms delay for audio system to settle
        
        # Play the beep (NOT included in recording)
        if self.current_event == CurrentEvent.RECORD_GREETING_VIA_HOOK:
            logger.info("Playing beep before greeting recording...")
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config["beep_volume"],
                0,
            )
        
        # Switch LEDs to red for recording and start immediately after beep
        if self.current_event == CurrentEvent.RECORD_GREETING_VIA_HOOK:
            self.led_animation_mode = "recording"  # Switch to red
            logger.info("Switched LED animation to recording mode (all red)")
        
        # Start recording the new greeting to a temp file
        if self.current_event == CurrentEvent.RECORD_GREETING_VIA_HOOK:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            greetings_dir = Path(self.config.get("recordings_path", "recordings")).parent / "sounds" / "greetings"
            greetings_dir.mkdir(parents=True, exist_ok=True)
            
            self.greeting_recording_file = str(greetings_dir / f"greeting-{timestamp}.wav")
            logger.info(f"Recording new greeting to: {self.greeting_recording_file}")
            
            # Start recording (no time limit for greeting)
            self.audio_interface.start_recording(self.greeting_recording_file)
            
            # Mark that recording has started AFTER it actually begins (so we know to save on hang-up)
            self.greeting_recording_started = True
            logger.info("Recording greeting... hang up when finished.")
    
    def _save_new_greeting(self, greeting_file):
        """
        Saves the newly recorded greeting and updates the config.
        """
        try:
            # Get relative path from base directory
            base_dir = Path(self.config.get("recordings_path", "recordings")).parent
            greeting_path = Path(greeting_file)
            
            if greeting_path.is_absolute():
                try:
                    relative_path = greeting_path.relative_to(base_dir)
                except ValueError:
                    # If file is not relative to base_dir, use absolute path
                    relative_path = greeting_path
            else:
                relative_path = greeting_path
            
            # Update in-memory config
            self.config["greeting"] = str(relative_path.as_posix())
            
            # Save to config.yaml using standard yaml module
            config_path = Path(self.config_path)
            
            with config_path.open("r") as f:
                config_data = yaml.safe_load(f)
            
            config_data["greeting"] = str(relative_path.as_posix())
            
            with config_path.open("w") as f:
                yaml.dump(config_data, f, default_flow_style=False)
            
            logger.info(f"Updated config with new greeting: {relative_path}")
            logger.info("Greeting saved successfully. It will be used for the next call.")
            
        except Exception as e:
            logger.error(f"Failed to update config with new greeting: {e}")
    
    def beep_and_record_greeting(self):
        """
        Plays the beep and start recording a new greeting message #, checking for the button event.
        """

        self.audio_interface.continue_playback = (
            self.current_event == CurrentEvent.RECORD_GREETING
        )

        # Play the beep
        if self.current_event == CurrentEvent.RECORD_GREETING:
            logger.info("Playing beep...")
            self.audio_interface.play_audio(
                self.config["beep"],
                self.config["beep_volume"],
                self.config["beep_start_delay"],
            )

        # Check if the record greeting message button is still pressed
        if self.current_event == CurrentEvent.RECORD_GREETING:
            path = str(Path(self.config["greeting"]))
            # Start recording new greeting message
            self.start_recording(path)

    def stop_recording_and_playback(self):
        """
        Stop recording and playback processes.
        """
        # Cancel the timer first to prevent any race conditions
        if hasattr(self, "timer") and self.timer is not None:
            self.timer.cancel()
            self.timer = None

        # Stop recording if it's active
        self.audio_interface.stop_recording()

        # Stop playback if the greeting thread is still running
        # Check if the attribute exists and is not None before checking is_alive()
        if hasattr(self, "greeting_thread") and self.greeting_thread is not None:
            try:
                if self.greeting_thread.is_alive():
                    logger.info("Stopping playback.")
                    self.audio_interface.continue_playback = False
                    self.audio_interface.stop_playback()

                    # Wait for the thread to complete with a longer timeout
                    self.greeting_thread.join(timeout=3.0)
            except (RuntimeError, AttributeError) as e:
                # Handle any race conditions where the thread might change state
                # between our check and the operation
                logger.warning(f"Error while stopping playback thread: {e}")

            # Force set to None to ensure clean state for next call
            self.greeting_thread = None

        # Ensure the hook listeners are still active
        logger.info("Verifying event listeners are active")

    def run(self):
        """
        Starts the main event loop waiting for phone hook events.
        """
        logger.info("System ready. Lift the handset to start.")
        try:
            pause()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            # Stop processing queue
            if AI_AVAILABLE and hasattr(self, 'processing_queue'):
                self.processing_queue.stop()
            # Cleanup LEDs
            self.led_cleanup()


if __name__ == "__main__":
    CONFIG_PATH = Path(__file__).parent / "../config.yaml"
    logger.info(f"Using configuration file: {CONFIG_PATH}")
    guest_book = AudioGuestBook(CONFIG_PATH)
    guest_book.run()
