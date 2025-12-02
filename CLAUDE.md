# Rotary Phone Audio Guestbook - AI Assistant Context

This file provides essential context for AI assistants (like Claude) working on this project.

## Project Overview

A Raspberry Pi-based audio guestbook system that transforms a vintage rotary phone into a voice recorder for special events (weddings, parties, etc.). When guests pick up the phone, they hear a greeting and can leave a voice message.

## Hardware Setup

- **Device**: Raspberry Pi Zero W
- **Hostname**: `camphone` or `camphone.local`
- **SSH Access**: Key-based authentication (no password required)
  ```bash
  ssh admin@camphone
  # or
  ssh admin@camphone.local
  ```
- **Web Interface**: `http://camphone.local:8080` or `http://camphone:8080`
- **Physical Components**: Rotary phone with hook switch, audio interface, LEDs

## Project Structure

```
rotary-phone-audio-guestbook/
├── src/                          # Core application code
│   ├── audioGuestBook.py        # Main recording logic
│   ├── audioInterface.py        # Audio playback/recording interface
│   └── bootLed.py               # LED boot status indicator
├── webserver/                    # Flask web application
│   ├── server.py                # Web server and API endpoints
│   ├── templates/               # HTML templates (Jinja2)
│   └── static/                  # CSS, JS, assets
├── sounds/                       # Audio files for prompts
│   ├── greetings/               # Greeting audio files
│   ├── beeps/                   # Beep sound files
│   └── time_exceeded/           # Time limit warning files
├── recordings/                   # Voice message recordings (WAV)
├── config.yaml                   # Main configuration file
├── *.service                     # systemd service files
└── docs/                         # Documentation
```

## Key Technologies

- **Python 3**: Core application language
- **Flask**: Web framework for settings interface
- **ALSA/arecord/aplay**: Audio recording and playback
- **GPIO**: Hardware interface for rotary phone hook switch
- **systemd**: Service management for auto-start
- **ffmpeg**: Audio format conversion (M4A, AAC, MP3 → WAV)

## Important Files

### Configuration
- `config.yaml` - Main config (GPIO pins, audio settings, file paths)
- `audioGuestBook.service` - Main recording service
- `audioGuestBookWebServer.service` - Web interface service

### Core Logic
- `src/audioGuestBook.py` - Handles phone pickup/hangup, plays greeting, records messages
- `src/audioInterface.py` - Wrapper for arecord/aplay audio commands
- `webserver/server.py` - Settings UI, file management, API endpoints

## Development Workflow

### Local Development
1. Edit files locally on macOS
2. Test changes (if possible locally)
3. Sync to Raspberry Pi

### Syncing to Raspberry Pi
```bash
# Simple sync (recommended for testing)
./sync-to-pi.sh camphone

# Or manually with rsync
rsync -avz --exclude-from='./rsync-exclude.txt' ./ admin@camphone:/home/admin/rotary-phone-audio-guestbook/
```

### Restarting Services
```bash
ssh admin@camphone
sudo systemctl restart audioGuestBook.service
sudo systemctl restart audioGuestBookWebServer.service
```

### Viewing Logs
```bash
ssh admin@camphone
sudo journalctl -u audioGuestBook.service -f
sudo journalctl -u audioGuestBookWebServer.service -f
```

## Common Tasks

### Deploy Changes
```bash
./deploy.sh  # Full deployment with backup
# or
./sync-to-pi.sh camphone  # Quick sync without backup
```

### Check Service Status
```bash
ssh admin@camphone "sudo systemctl status audioGuestBook.service audioGuestBookWebServer.service"
```

### Backup Recordings
```bash
rsync -avz admin@camphone:/home/admin/rotary-phone-audio-guestbook/recordings/ ./local-backup/
```

### Test Audio Playback
```bash
ssh admin@camphone
aplay -D plughw:1,0 /home/admin/rotary-phone-audio-guestbook/sounds/greetings/default.wav
```

## Configuration Settings

Key `config.yaml` parameters:
- `alsa_hw_mapping`: Audio device (e.g., `plughw:1,0`)
- `hook_gpio`: GPIO pin for phone hook switch (default: 22)
- `greeting`, `beep`, `time_exceeded`: Audio file paths
- `recording_limit`: Max recording duration in seconds
- `sample_rate`, `channels`: Audio quality settings

## Recent Features

### Multi-Greeting Management (v1.1+)
- Upload audio files in multiple formats (WAV, M4A, AAC, MP3)
- Auto-converts to WAV using ffmpeg
- Manage multiple greetings/beeps via web interface
- Preview and delete audio files
- Located in branch: `feature/multi-greeting-management`

### LED Boot Indicator (v1.0)
- Visual feedback during boot process
- Shows system status via LED patterns

## Dependencies

### System Packages (on Raspberry Pi)
- `python3`, `python3-pip`
- `alsa-utils` (arecord, aplay, amixer)
- `ffmpeg` (for audio format conversion)
- `sox` (audio manipulation)
- `python3-rpi.gpio` or `gpiozero`

### Python Packages
- `flask`
- `ruamel.yaml`
- `psutil`
- `RPi.GPIO` or `gpiozero`

Install with:
```bash
ssh admin@camphone
pip3 install -r requirements.txt
```

## Troubleshooting

### Service Won't Start
```bash
ssh admin@camphone
sudo systemctl status audioGuestBook.service
sudo journalctl -u audioGuestBook.service --no-pager -n 50
```

### No Audio Output
- Check ALSA device: `aplay -l`
- Test playback: `aplay -D plughw:1,0 test.wav`
- Check volume: `amixer scontrols` and `amixer get Speaker`

### Web Interface Not Accessible
- Check service: `sudo systemctl status audioGuestBookWebServer.service`
- Check port: `sudo netstat -tlnp | grep 8080`
- Check firewall: `sudo ufw status`

### ffmpeg Not Found
```bash
ssh admin@camphone
sudo apt-get update
sudo apt-get install ffmpeg
```

## Git Workflow

### Branches
- `main` - Stable, deployed code
- `feature/*` - New features in development
- Tagged releases: `v1.0`, `v1.0.1`, etc.

### Creating a Feature
```bash
git checkout -b feature/my-new-feature
# Make changes
git add -A
git commit -m "Add my feature"
```

### Testing Before Merge
```bash
git checkout feature/my-new-feature
./sync-to-pi.sh camphone
# Test on device
# If working, merge to main
```

## Web Interface Endpoints

- `GET /` - Recordings list view
- `GET /config` - Settings/configuration page
- `POST /config` - Update configuration
- `GET /api/recordings` - List recordings (JSON)
- `GET /recordings/<filename>` - Stream recording file
- `POST /delete/<filename>` - Delete recording
- `POST /delete-audio/<type>/<filename>` - Delete audio file (greeting/beep/time_exceeded)
- `GET /sounds/<type>/<filename>` - Stream sound file for preview
- `GET /download-all` - Download all recordings as ZIP
- `POST /reboot` - Reboot system
- `POST /shutdown` - Shutdown system

## Security Notes

- Web interface has no authentication (runs on local network only)
- SSH uses key-based auth (no password)
- Admin user has sudo access
- Services run as admin user (not root)

## Performance Considerations

- Raspberry Pi Zero W is low-powered
- Large file conversions (ffmpeg) may take time
- Recordings stored as WAV (uncompressed, larger files)
- Web interface uses streaming for audio playback

## Testing Checklist

When making changes, test:
- [ ] Phone pickup triggers greeting
- [ ] Recording starts after beep
- [ ] Phone hangup stops recording
- [ ] Web interface loads at :8080
- [ ] Can download recordings
- [ ] Settings persist after reboot
- [ ] Services auto-start on boot
- [ ] LED indicators work (if applicable)

## AI Assistant Guidelines

When working on this project:

1. **Always check if syncing to Pi is needed** after code changes
2. **Service restarts are required** for most Python changes to take effect
3. **Test on the actual hardware** - audio and GPIO can't be fully simulated
4. **Check logs first** when debugging - `journalctl` is your friend
5. **Be mindful of file paths** - use absolute paths or relative to BASE_DIR
6. **Audio format matters** - the system expects WAV files for playback
7. **Don't commit recordings/** - it's in .gitignore
8. **Consider the Pi's limitations** - it's not a powerful device

## External Resources

- [GPIO Pin Reference](https://pinout.xyz/)
- [ALSA Documentation](https://alsa-project.org/wiki/Main_Page)
- [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/)
- [Flask Documentation](https://flask.palletsprojects.com/)

## Contact

For questions about this project, refer to README.md or check existing issues/documentation.
