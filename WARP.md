# Rotary Phone Audio Guestbook - Warp AI Context

This file provides essential context for Warp AI when working on this project.

## Project Overview

A Raspberry Pi-based audio guestbook system that transforms a vintage rotary phone into an intelligent voice recorder for events. Guests pick up the phone, hear a greeting, leave a message, and the system automatically transcribes and categorizes recordings using AI.

## Hardware & Environment

- **Device**: Raspberry Pi Zero W (single-core, limited resources)
- **Hostname**: `camphone` or `camphone.local`
- **SSH**: Key-based authentication
  ```bash
  ssh admin@camphone
  ```
- **Web Interface**: http://camphone.local:8080
- **Components**: Rotary phone, hook switch, audio interface, WS2811 LED strip

## Project Structure

```
rotary-phone-audio-guestbook/
├── src/                              # Core application
│   ├── audioGuestBook.py            # Main logic (phone events, recording, AI integration)
│   ├── audioInterface.py            # ALSA audio wrapper
│   └── bootLed.py                   # LED boot indicator
├── webserver/                        # Flask web app + AI processors
│   ├── server.py                    # API endpoints, file management
│   ├── metadata_manager.py          # Thread-safe JSON metadata storage
│   ├── openai_processor.py          # Whisper + GPT-4o Mini integration
│   ├── job_queue.py                 # Background AI processing queue
│   ├── connectivity_checker.py      # Internet availability checking
│   ├── templates/                   # Jinja2 HTML templates
│   └── static/                      # Frontend assets (JS, CSS)
├── sounds/                           # Audio files (greetings, beeps)
├── recordings/                       # Voice recordings (WAV + metadata JSON)
├── config.yaml                       # Configuration (GPIO, audio, AI settings)
├── *.service                         # systemd service files
├── deploy.sh                         # Full deployment with dependency install
└── sync-to-pi.sh                    # Quick code sync without restart
```

## Key Technologies

- **Python 3**: Core application
- **Flask**: Web framework
- **OpenAI API**: Whisper (transcription) + GPT-4o Mini (metadata extraction)
- **ALSA**: Audio recording/playback
- **FFmpeg**: Audio compression (WAV → MP3 for bandwidth optimization)
- **GPIO/gpiozero**: Hardware interface
- **systemd**: Service management

## Recent Features (v2.1+)

### OpenAI AI Processing Integration
- **Automatic transcription** using Whisper API
- **Metadata extraction** via GPT-4o Mini:
  - Speaker names
  - Emotional categories (joyful, heartfelt, humorous, etc.)
  - AI-generated titles/summaries
  - Confidence scores
- **Audio compression**: WAV → MP3 (98% bandwidth reduction)
- **Smart processing**: Cooldown periods, idle-time detection
- **Retry logic**: Automatic retries with exponential backoff
- **Status tracking**: Pending → Processing → Completed

**Configuration** (in `config.yaml`):
```yaml
openai_enabled: false                       # Enable AI features
openai_processing_cooldown: 0               # Immediate processing (Phase 2 test)
openai_allow_processing_during_call: true   # Process while phone in use
openai_compress_audio: true                 # 98% bandwidth savings
```

**See**: `OPENAI_INTEGRATION_SUMMARY.md` and `OPENAI_ENHANCEMENTS.md`

## Deployment Workflow

### Option 1: Full Deploy (Recommended for updates)
**Syncs code + installs dependencies + restarts services**

```bash
./deploy.sh camphone
```

This script:
1. Syncs all files to Pi
2. Installs FFmpeg (for audio compression)
3. Installs Python packages (`openai`, `requests`)
4. Copies service files
5. Restarts both services

### Option 2: Quick Sync (For minor changes)
**Only syncs code, no restart**

```bash
./sync-to-pi.sh camphone
```

Then manually restart if needed:
```bash
ssh admin@camphone "sudo systemctl restart audioGuestBook.service audioGuestBookWebServer.service"
```

### After Deployment

1. **Check service status**:
   ```bash
   ssh admin@camphone "sudo systemctl status audioGuestBook.service audioGuestBookWebServer.service"
   ```

2. **Monitor logs**:
   ```bash
   ssh admin@camphone
   sudo journalctl -u audioGuestBook.service -f
   # Look for "AI processing queue initialized" message
   ```

3. **Test web interface**: http://camphone:8080

## Common Development Tasks

### View Logs (Real-time)
```bash
ssh admin@camphone
# Main application logs
sudo journalctl -u audioGuestBook.service -f

# Web server logs  
sudo journalctl -u audioGuestBookWebServer.service -f

# Filter for OpenAI processing
sudo journalctl -u audioGuestBook.service -f | grep -i "openai\|processing\|compress"
```

### Restart Services
```bash
ssh admin@camphone
sudo systemctl restart audioGuestBook.service
sudo systemctl restart audioGuestBookWebServer.service
```

### Check System Resources (Pi Zero W)
```bash
ssh admin@camphone
htop  # CPU and memory usage
```

### Backup Recordings
```bash
# Pull recordings from Pi to local
rsync -avz admin@camphone:/home/admin/rotary-phone-audio-guestbook/recordings/ ./local-backup/

# Also backs up metadata JSON
```

### Test Audio
```bash
ssh admin@camphone
# Test playback
aplay -D plughw:1,0 /home/admin/rotary-phone-audio-guestbook/sounds/greetings/default.wav

# Check audio devices
aplay -l

# Check volume
amixer get Speaker
```

## Configuration Management

### Key Settings (`config.yaml`)

**Hardware**:
- `alsa_hw_mapping`: Audio device (default: `plughw:1,0`)
- `hook_gpio`: Phone hook switch pin (default: 22)

**Audio**:
- `greeting`, `beep`, `time_exceeded`: Audio file paths
- `recording_limit`: Max duration (seconds)
- `sample_rate`, `channels`: Audio quality

**AI Processing** (NEW):
- `openai_enabled`: Master toggle
- `openai_api_key`: OpenAI API key (get at platform.openai.com)
- `openai_processing_cooldown`: Delay before processing (0 = immediate)
- `openai_allow_processing_during_call`: Process while recording
- `openai_compress_audio`: WAV → MP3 conversion (saves bandwidth)

### Editing Config
```bash
# Edit locally, then deploy
vim config.yaml
./deploy.sh camphone

# Or edit directly on Pi
ssh admin@camphone
nano /home/admin/rotary-phone-audio-guestbook/config.yaml
# Restart service for changes to take effect
```

## OpenAI Integration Details

### Setup Requirements

1. **Install dependencies** (done automatically by `deploy.sh`):
   ```bash
   sudo apt-get install ffmpeg
   pip3 install openai requests
   ```

2. **Get API key**: https://platform.openai.com/api-keys

3. **Configure** in `config.yaml`:
   ```yaml
   openai_enabled: true
   openai_api_key: "sk-proj-..."
   ```

### Processing Flow

1. **Recording finishes** → Saved as WAV
2. **Queued for processing** → Added to background queue
3. **Wait conditions met**:
   - Phone is idle (unless `allow_processing_during_call: true`)
   - Cooldown period passed
   - Internet available
4. **Compress audio**: WAV → MP3 (if enabled)
5. **Transcribe**: Upload to Whisper API
6. **Extract metadata**: GPT-4o Mini analyzes transcription
7. **Store results**: Save to `recordings_metadata.json`
8. **Display in UI**: Shows on web interface

### Current Test Mode (Phase 2)

**Settings**:
- `openai_processing_cooldown: 0` - Immediate processing
- `openai_allow_processing_during_call: true` - Process during calls

**Purpose**: Test if Pi Zero W can handle async processing

**What to watch**:
- Audio quality during simultaneous record + process
- System responsiveness
- Any crackling or stuttering

**Fallback if issues** (edit `config.yaml`):
```yaml
openai_processing_cooldown: 120
openai_allow_processing_during_call: false
```

## API Endpoints

### Recordings
- `GET /api/recordings` - List with AI metadata (JSON)
- `GET /recordings/<filename>` - Stream audio file
- `GET /api/transcription/<filename>` - Get full transcription
- `POST /delete/<filename>` - Delete recording
- `POST /delete-recordings` - Bulk delete
- `POST /api/process-pending` - Manually process pending recordings

### System
- `GET /` - Recordings list (web UI)
- `GET /config` - Settings page
- `POST /config` - Update settings
- `POST /reboot` - Reboot Pi
- `POST /shutdown` - Shutdown Pi

## Troubleshooting

### Services Won't Start
```bash
ssh admin@camphone
sudo systemctl status audioGuestBook.service
sudo journalctl -u audioGuestBook.service --no-pager -n 100
```

### OpenAI Processing Not Working
```bash
# Check if enabled
ssh admin@camphone
grep "openai_enabled" /home/admin/rotary-phone-audio-guestbook/config.yaml

# Check logs for errors
sudo journalctl -u audioGuestBook.service | grep -i "openai\|error"

# Verify dependencies
pip3 list | grep openai
which ffmpeg
```

### FFmpeg Not Found
```bash
ssh admin@camphone
sudo apt-get update
sudo apt-get install ffmpeg
```

### Audio Compression Failing
**Symptom**: Logs show "FFmpeg compression failed"

**Quick fix**: Disable compression temporarily
```yaml
openai_compress_audio: false
```

### Performance Issues (Pi Zero W)
**Symptom**: Audio crackling during processing

**Solution**: Switch to idle-only processing
```yaml
openai_processing_cooldown: 120
openai_allow_processing_during_call: false
```

### No Internet / API Failures
- Recordings marked as "pending"
- Use "Process Now" button in web UI when internet returns
- Check retry settings: `openai_max_retries`, `openai_retry_delay`

## Testing Checklist

### Basic Functionality
- [ ] Phone pickup triggers greeting
- [ ] Recording starts after beep
- [ ] Phone hangup stops recording
- [ ] Recordings appear in web interface
- [ ] Can play recordings
- [ ] Can delete recordings

### AI Features (if enabled)
- [ ] Processing starts after recording
- [ ] Logs show "Compressing..." message
- [ ] Logs show "Transcribing..." message
- [ ] Logs show "Extracting metadata..." message
- [ ] Web UI shows AI-generated title
- [ ] Speaker names displayed
- [ ] Category badge shown
- [ ] Click title shows transcription modal
- [ ] Processing status indicators work

### Performance (Pi Zero W)
- [ ] Audio quality perfect during processing
- [ ] No system slowdown
- [ ] No recording failures
- [ ] Services remain responsive

## Git Workflow

### Current Branch Strategy
- `main` - Stable releases (v2.1 tagged)
- `openai-tts-implementation` - Current feature branch (OpenAI integration)

### Working on Features
```bash
# Already on feature branch
git status

# Make changes
git add -A
git commit -m "Description of changes"
git push brian-slate openai-tts-implementation

# Deploy to test
./deploy.sh camphone
```

## Warp AI Guidelines

When assisting with this project:

1. **Always use deployment scripts**: `deploy.sh` or `sync-to-pi.sh`
2. **Service restarts required**: Most Python changes need service restart
3. **Check logs first**: Use `journalctl` for debugging
4. **Mind Pi Zero W limitations**: Single-core, limited RAM
5. **Test on actual hardware**: Audio/GPIO require real device
6. **OpenAI costs money**: Be aware when enabling/testing AI features
7. **Configuration is critical**: Most issues are config-related
8. **Compression is essential**: Without it, Pi Zero W bandwidth struggles

### Quick Commands Reference

```bash
# Deploy with dependencies
./deploy.sh camphone

# Quick sync only
./sync-to-pi.sh camphone

# View logs
ssh admin@camphone "sudo journalctl -u audioGuestBook.service -f"

# Restart services
ssh admin@camphone "sudo systemctl restart audioGuestBook.service audioGuestBookWebServer.service"

# Check status
ssh admin@camphone "sudo systemctl status audioGuestBook.service audioGuestBookWebServer.service"

# Monitor resources
ssh admin@camphone "htop"

# Edit config
vim config.yaml && ./deploy.sh camphone
```

## Dependencies

### System Packages (on Raspberry Pi)
- `python3`, `python3-pip`
- `alsa-utils` (arecord, aplay, amixer)
- `ffmpeg` (for audio format conversion and compression)
- `sox` (audio manipulation)
- `python3-rpi.gpio` or `gpiozero`

### Python Packages
Managed via `pyproject.toml` and `requirements.txt`:
- `flask` - Web framework
- `gunicorn` - WSGI server
- `gevent` - Async library
- `gpiozero` - GPIO interface
- `ruamel-yaml` - YAML parsing
- `psutil` - System monitoring
- `openai` - OpenAI API client (AI features)
- `requests` - HTTP library (connectivity checking)

Install with:
```bash
ssh admin@camphone
pip3 install -r requirements.txt
```

## External Documentation

- `OPENAI_INTEGRATION_SUMMARY.md` - Complete AI integration guide
- `OPENAI_ENHANCEMENTS.md` - Performance optimizations details
- `OPENAI_IMPLEMENTATION_PLAN.md` - Original implementation spec
- `README.md` - General project documentation
- `docs/` - Hardware, software, and configuration guides
- `CLAUDE.md` - Legacy AI assistant context (being replaced by WARP.md)

## Security Notes

- Web interface has no authentication (local network only)
- SSH uses key-based auth
- OpenAI API key stored in plain text in config.yaml (local only)
- Services run as `admin` user (not root)

## Performance Expectations

### Pi Zero W (Current Hardware)
- **Recording**: Always works, hardware-accelerated
- **Web Interface**: Responsive for file management
- **AI Processing**: Test mode (async during calls) - monitoring for issues
- **Compression**: Fast (~0.5s per minute of audio)
- **Upload**: Much faster with compression (0.12 MB vs 10 MB)

### Recommended Settings by Pi Model
- **Pi Zero/Zero 2**: `cooldown: 120`, `allow_during_call: false`
- **Pi 3**: `cooldown: 60`, `allow_during_call: false` (test true)
- **Pi 4/5**: `cooldown: 0`, `allow_during_call: true`

## Contact & Support

For questions about this project:
- Check existing documentation
- Review logs: `journalctl`
- Test configuration changes incrementally
- Monitor system resources during testing
