# Recording Filtering Implementation Guide

## Overview
This document outlines the changes needed to prevent storing empty or very short recordings where users hang up early or no audio is captured.

## Problem
Currently, the system saves all recordings regardless of duration or content, resulting in junk recordings where:
- Users hang up during or immediately after the beep
- No actual message is left
- Recording files are empty or very small

## Solution Strategy
Implement intelligent filtering based on:
1. **Known audio durations** - Calculate minimum valid recording time based on actual greeting/beep durations
2. **Recording duration check** - Track how long the recording lasted
3. **File size validation** - Ensure file has actual content

## Configuration Changes

### `config.yaml`
Add new configuration parameters:

```yaml
# Recording validation settings
minimum_message_duration: 3.0  # Minimum seconds of actual user message required
minimum_file_size_bytes: 50000  # Minimum file size (50KB) to be considered valid
delete_invalid_recordings: true  # Whether to delete invalid recordings (set false to keep for debugging)
```

## Code Changes

### 1. AudioInterface Class (`src/audioInterface.py`)

#### Add new instance variables in `__init__`:
```python
def __init__(
    self,
    alsa_hw_mapping,
    format,
    file_type,
    recording_limit,
    sample_rate=44100,
    channels=1,
    mixer_control_name="Speaker",
    minimum_message_duration=3.0,
    minimum_file_size_bytes=50000,
    delete_invalid_recordings=True,
):
    # ... existing code ...
    self.minimum_message_duration = minimum_message_duration
    self.minimum_file_size_bytes = minimum_file_size_bytes
    self.delete_invalid_recordings = delete_invalid_recordings
    self.recording_start_time = None
```

#### Add helper method to get audio duration:
```python
def get_audio_duration(self, audio_file):
    """
    Gets the duration of an audio file using soxi.
    
    Args:
        audio_file (str): Path to the audio file
        
    Returns:
        float: Duration in seconds, or 0.0 if unable to determine
    """
    try:
        result = subprocess.run(
            ["soxi", "-D", str(audio_file)],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
        logger.error(f"Error getting duration for {audio_file}: {e}")
        return 0.0
```

#### Add method to calculate minimum recording duration:
```python
def calculate_minimum_recording_duration(self, beep_file, beep_include_in_message):
    """
    Calculates the minimum valid recording duration based on beep settings.
    
    Args:
        beep_file (str): Path to the beep audio file
        beep_include_in_message (bool): Whether beep is included in recording
        
    Returns:
        float: Minimum duration in seconds for a valid recording
    """
    beep_duration = self.get_audio_duration(beep_file)
    
    if beep_include_in_message:
        # Recording includes beep, so minimum = beep + message duration
        minimum = beep_duration + self.minimum_message_duration
        logger.info(f"Minimum recording duration: {minimum:.2f}s (beep: {beep_duration:.2f}s + message: {self.minimum_message_duration:.2f}s)")
    else:
        # Recording starts after beep, so minimum = just message duration
        minimum = self.minimum_message_duration
        logger.info(f"Minimum recording duration: {minimum:.2f}s (message only, beep not included)")
    
    return minimum
```

#### Modify `start_recording` method:
Add timestamp tracking at the beginning:
```python
def start_recording(self, output_file):
    """
    Starts recording audio to the specified file in a non-blocking manner.
    """
    # Track recording start time
    self.recording_start_time = time.time()
    
    # ... rest of existing code ...
```

#### Modify `stop_recording` method:
Add validation logic after the recording stops (after line 228/254 where file size is already checked):

```python
def stop_recording(self):
    """
    Stops the ongoing audio recording process and validates the recording.
    """
    if self.recording_process:
        logger.info(f"Stopping recording process with PID: {self.recording_process.pid}")
        
        # Get the output file name before we lose the process
        command = self.recording_process.args
        output_file = command[-1] if len(command) > 0 else None
        
        try:
            # ... existing SIGINT/termination code ...
            
            # After recording is stopped, validate the recording
            if output_file and os.path.exists(output_file):
                self._validate_and_cleanup_recording(output_file)
            
        except (ProcessLookupError, subprocess.SubprocessError) as e:
            logger.warning(f"Error while terminating recording process: {e}")
        
        # ... rest of existing cleanup code ...
```

#### Add validation method:
```python
def _validate_and_cleanup_recording(self, output_file):
    """
    Validates a recording file and deletes it if invalid.
    
    Args:
        output_file (str): Path to the recording file to validate
    """
    if not self.delete_invalid_recordings:
        logger.info("Recording validation disabled, keeping file")
        return
    
    is_valid = True
    reasons = []
    
    # Check 1: File size
    try:
        file_size = os.path.getsize(output_file)
        if file_size < self.minimum_file_size_bytes:
            is_valid = False
            reasons.append(f"file size too small ({file_size} bytes < {self.minimum_file_size_bytes} bytes)")
    except OSError as e:
        logger.error(f"Error checking file size: {e}")
        return
    
    # Check 2: Recording duration
    if self.recording_start_time is not None:
        recording_duration = time.time() - self.recording_start_time
        if hasattr(self, 'minimum_recording_duration_threshold'):
            if recording_duration < self.minimum_recording_duration_threshold:
                is_valid = False
                reasons.append(f"recording too short ({recording_duration:.2f}s < {self.minimum_recording_duration_threshold:.2f}s)")
    
    # Delete if invalid
    if not is_valid:
        try:
            os.remove(output_file)
            logger.info(f"Deleted invalid recording: {output_file} - Reasons: {', '.join(reasons)}")
        except OSError as e:
            logger.error(f"Error deleting invalid recording {output_file}: {e}")
    else:
        logger.info(f"Recording validated successfully: {output_file} ({file_size} bytes)")
    
    # Reset tracking
    self.recording_start_time = None
```

### 2. AudioGuestBook Class (`src/audioGuestBook.py`)

#### Modify `__init__` to pass new parameters to AudioInterface:
```python
def __init__(self, config_path):
    # ... existing code ...
    
    self.audio_interface = AudioInterface(
        alsa_hw_mapping=self.config["alsa_hw_mapping"],
        format=self.config["format"],
        file_type=self.config["file_type"],
        recording_limit=self.config["recording_limit"],
        sample_rate=self.config["sample_rate"],
        channels=self.config["channels"],
        mixer_control_name=self.config["mixer_control_name"],
        minimum_message_duration=self.config.get("minimum_message_duration", 3.0),
        minimum_file_size_bytes=self.config.get("minimum_file_size_bytes", 50000),
        delete_invalid_recordings=self.config.get("delete_invalid_recordings", True),
    )
    
    # Calculate and set minimum recording duration threshold
    minimum_duration = self.audio_interface.calculate_minimum_recording_duration(
        self.config["beep"],
        self.config["beep_include_in_message"]
    )
    self.audio_interface.minimum_recording_duration_threshold = minimum_duration
```

## Testing Plan

### 1. Test with valid recordings
- Pick up phone, leave 5+ second message
- Verify recording is saved

### 2. Test with early hang-ups
- Pick up phone, hang up during greeting
- Pick up phone, hang up during beep
- Pick up phone, hang up 1-2 seconds after beep
- Verify these recordings are deleted and logged

### 3. Test with silent recordings
- Pick up phone, stay silent for 30 seconds, hang up
- This should be saved (duration is valid, even if silent)
- Consider future enhancement to check audio levels if needed

### 4. Test configuration
- Set `delete_invalid_recordings: false`
- Make short recording
- Verify it's kept (for debugging)

### 5. Check logs
- Review log output to confirm validation messages appear
- Verify deletion reasons are clear

## Dependencies

Ensure `sox` is installed (for `soxi` command):
```bash
# Raspberry Pi
sudo apt-get install sox

# macOS (for development/testing)
brew install sox
```

## Future Enhancements

### Audio Level Detection (Optional)
If silent recordings become an issue, add audio level analysis:
```python
def has_audio_content(self, audio_file, threshold_db=-40):
    """
    Checks if audio file has meaningful content above silence threshold.
    """
    try:
        result = subprocess.run(
            ["sox", audio_file, "-n", "stat"],
            capture_output=True,
            text=True,
            check=False
        )
        # Parse output for "Maximum amplitude" or "RMS amplitude"
        # Return False if below threshold
    except Exception as e:
        logger.error(f"Error analyzing audio levels: {e}")
        return True  # Assume valid if can't check
```

## Rollback Plan

If issues arise:
1. Set `delete_invalid_recordings: false` in config.yaml
2. Review log files to see what's being filtered
3. Adjust `minimum_message_duration` or `minimum_file_size_bytes` thresholds
4. Re-enable by setting `delete_invalid_recordings: true`

## Summary of Files to Modify

1. **config.yaml** - Add 3 new configuration parameters
2. **src/audioInterface.py** - Add validation logic and helper methods
3. **src/audioGuestBook.py** - Pass configuration to AudioInterface and calculate minimum duration

## Implementation Order

1. Add configuration parameters to config.yaml
2. Update AudioInterface class with new methods
3. Update AudioGuestBook initialization
4. Test thoroughly with various scenarios
5. Monitor logs after deployment
