# AI Processing Implementation Fixes - December 2, 2025

## Issues Resolved

### 1. Dependency Management Architecture
**Problem:** Inconsistent Python environments between services
- audioGuestBook service: Ran as root, used system Python
- audioGuestBookWebServer service: Ran as admin, used venv

**Solution:** Unified both services to use shared venv
- Updated audioGuestBook.service to run as `admin` user
- Changed ExecStart to use `.venv/bin/python3`
- Added GPIO group membership for hardware access
- Updated deploy.sh to:
  - Create venv if missing
  - Install all packages into venv
  - Force install on new venv creation
  - Track requirements.txt changes via MD5

### 2. Missing Python Packages
**Problems:** Multiple missing dependencies caused service crashes

**Fixed by adding to requirements.txt:**
- `pyyaml==6.0.2` - For config file parsing (audioGuestBook.py)
- `rpi-gpio==0.7.1` - Raspberry Pi GPIO control
- `adafruit-circuitpython-neopixel==6.3.11` - LED strip control
- `adafruit-blinka==8.47.0` - Provides `board` module

### 3. Web Server Module Import Issues
**Problem:** Web server couldn't import metadata_manager, openai_processor

**Solution:** Added PYTHONPATH to start_server.sh
```bash
export PYTHONPATH=/home/admin/rotary-phone-audio-guestbook/webserver:$PYTHONPATH
```

### 4. OpenAI API Parameter Incompatibilities
**Problem:** API calls failing with newer models

**Issues Fixed:**
1. `max_tokens` deprecated → Changed to `max_completion_tokens`
2. `temperature` not supported on some models → Removed parameter
3. Model `gpt-5-mini` doesn't exist → Changed to `gpt-4o-mini`

**Files Modified:**
- `webserver/openai_processor.py`:
  - Line 192: Changed `max_tokens=200` to `max_completion_tokens=200`
  - Line 191: Removed `temperature=0.3,`
  - Added error logging for empty/invalid GPT responses

### 5. Config Validation Bug
**Problem:** API key validation triggered on form submit even when unchanged

**Solution:** Updated server.py validation logic
- Skip validation if field is empty but key exists in config
- JavaScript form submit handler restores full API key from masked value
- Only validate when key actually changes

**Files Modified:**
- `webserver/server.py`: Lines 312-341
- `webserver/templates/config.html`: Lines 951-961

### 6. Error Banner Implementation
**Problem:** Users couldn't see AI processing errors

**Solution:** Global error banner system
- `job_queue.py`: Tracks last error in `last_openai_error.json`
- `server.py`: Context processor injects error to templates
- `base.html`: Shows banner on all pages when AI enabled + error exists
- Clears on:
  - Valid API key saved
  - AI processing disabled
  - Next successful processing

## Final Working Configuration

### Service Files
Both services now:
- Run as `admin` user
- Use `.venv/bin/python3`
- Have consistent environment

### Requirements.txt
Complete list of dependencies:
- Core: flask, gunicorn, gevent, requests, openai
- Hardware: gpiozero, rpi-gpio, adafruit-blinka, adafruit-circuitpython-neopixel
- Utilities: pyyaml, ruamel-yaml, psutil

### Deploy Script
Now properly:
1. Creates venv if missing
2. Installs python3-venv system package
3. Adds user to gpio group
4. Installs all packages into venv
5. Tracks changes via MD5 hash

## Testing Performed

### Successful Test
Recording: `2025-12-01T23:49:37.152753.wav`

**Results:**
```json
{
  "transcription": "Hi, this is Brian Slate, leaving a message for Cam and Lara...",
  "speaker_names": ["Brian", "Cam", "Lara"],
  "category": "joyful",
  "summary": "Happy message for the couple",
  "confidence": 0.95,
  "processing_status": "completed"
}
```

**Verified:**
- ✅ Whisper transcription works
- ✅ GPT-4o-mini metadata extraction works
- ✅ Audio compression (WAV → MP3)
- ✅ Metadata storage in JSON
- ✅ Web API returns full metadata
- ✅ Services run reliably

## Remaining Known Issues

### LED Permission Denied
**Issue:** Service can't access `/dev/mem` for NeoPixel LEDs

**Status:** Non-critical, LEDs are optional
**Potential Fix:** Either:
1. Add udev rules for /dev/mem
2. Run LED control in separate service with elevated permissions
3. Use rpi_ws281x library instead (doesn't need /dev/mem)

## Files Modified

1. `audioGuestBook.service` - Added User/Group, changed to venv Python
2. `deploy.sh` - Enhanced venv creation and package installation
3. `start_server.sh` - Added PYTHONPATH export
4. `requirements.txt` - Added missing packages
5. `webserver/openai_processor.py` - Fixed API parameters
6. `webserver/server.py` - Fixed config validation
7. `webserver/templates/config.html` - Added form submit handler
8. `webserver/templates/base.html` - Added error banner
9. `webserver/job_queue.py` - Added error tracking

## Best Practices Established

1. **Single venv for all services** - Consistency and easier management
2. **Explicit PYTHONPATH** - Clear module resolution
3. **requirements.txt with pinned versions** - Reproducible builds
4. **MD5 tracking** - Skip reinstalls when unchanged
5. **User-level services** - Better security (no root except for GPIO)
6. **Error persistence** - User visibility without auto-disabling features

## Migration Notes

If upgrading from pre-v2.1:
```bash
# Remove old system packages (optional)
ssh admin@camphone
sudo pip3 uninstall openai requests pyyaml

# Deploy new version
./deploy.sh camphone

# Service will recreate venv and install all deps
```
