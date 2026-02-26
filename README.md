# Rotary Phone Audio Guestbook

An intelligent audio recording system that transforms a vintage rotary phone into an AI-powered voice recorder for events. Guests pick up the phone, hear a customizable greeting, leave a message, and the system automatically transcribes and categorizes recordings using OpenAI's Whisper and GPT models.

## Features

### Core Functionality
- **Vintage Rotary Phone Interface** - Uses authentic rotary phone hardware with hook switch detection
- **High-Quality Audio Recording** - Records messages up to 300 seconds in CD-quality WAV format
- **Custom Greetings** - Play personalized greeting messages with multiple modes (single, random, sequential)
- **LED Status Indicators** - WS2811 LED strip provides visual feedback for recording and AI processing status
- **Recording Validation** - Automatically filters out accidental recordings based on duration and file size
- **Web-Based Management** - Modern, responsive web interface for playback, management, and configuration

### AI-Powered Features
- **Automatic Transcription** - OpenAI Whisper API converts voice to text
- **Speaker Detection** - Identifies and labels individual speakers in recordings
- **Emotional Categorization** - Classifies messages by emotion (joyful, heartfelt, humorous, nostalgic, etc.)
- **AI-Generated Summaries** - Creates concise titles and descriptions for each recording
- **Smart Processing** - Configurable cooldown periods and idle-time detection optimize performance
- **Audio Compression** - Converts WAV to MP3 (98% bandwidth reduction) before cloud processing
- **Offline Resilience** - Queues recordings for processing when internet connectivity returns
- **Manual Processing Control** - "Process Now" button for on-demand AI processing

### Advanced Configuration
- **Multiple Greeting Modes** - Single greeting, random selection, or sequential rotation
- **Flexible GPIO Control** - Configurable pins for hook switch, recording button, and shutdown
- **Custom Audio Files** - Upload your own greeting, beep, and timeout messages
- **Password Protection** - Optional web interface authentication
- **WiFi Management (Web UI)** - Scan/add/delete WiFi networks and set priorities from the Settings page
- **Recording Filters** - Set minimum duration and file size thresholds
- **AI Customization** - Configure ignored names (e.g., bride/groom), categories, and language settings

## Hardware Requirements

### Essential Components
- **Raspberry Pi** - Any model (Zero, 3, 4, 5); Pi 4/5 recommended for AI processing
- **Vintage Rotary Phone** - With hook switch and handset
- **USB Audio Interface** - For microphone and speaker connection
- **Micro SD Card** - 16GB+ for recordings and system
- **Power Supply** - Appropriate for your Pi model

### Optional Components
- **WS2811 LED Strip** - For visual status indicators (13 LEDs)
- **Lavalier Microphone** - Upgrade from carbon mic for better audio quality
- **LiPo Battery + Charger** - For portable, battery-powered operation
- **Momentary Button** - For recording custom greetings

See [Materials Guide](docs/materials.md) for detailed parts list and sourcing.

## Quick Start

### 1. Hardware Assembly
Follow the [Hardware Guide](docs/hardware.md) for detailed wiring instructions:
- Connect hook switch to GPIO 22 and GND
- Wire handset to USB audio interface
- (Optional) Connect LED strip to GPIO 18
- (Optional) Add recording button on GPIO 23

### 2. Software Installation

#### Option A: Pre-built Image (Recommended)
1. Download the latest release image from the [releases page](https://github.com/brianslate/rotary-phone-audio-guestbook/releases)
2. Flash to SD card using Raspberry Pi Imager or Balena Etcher
3. Configure WiFi and credentials during first boot
4. Insert SD card and power on

#### Option B: Manual Installation
```bash
# Clone repository
git clone https://github.com/brianslate/rotary-phone-audio-guestbook.git
cd rotary-phone-audio-guestbook

# Install system dependencies
sudo apt-get update
sudo apt-get install -y ffmpeg alsa-utils python3-pip

# Install Python dependencies
pip3 install -r requirements.txt

# Install frontend dependencies and build CSS
cd webserver
npm ci
npm run build
cd ..

# Configure settings
cp config.yaml.template config.yaml
nano config.yaml  # Edit your configuration

# Set up systemd services
sudo cp *.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable audioGuestBook.service audioGuestBookWebServer.service
sudo systemctl start audioGuestBook.service audioGuestBookWebServer.service
```

### 3. Initial Configuration

1. Access web interface at `http://<raspberry-pi-ip>:8080`
2. Navigate to Settings page
3. Configure essential settings:
   - **Audio devices**: Verify ALSA hardware mapping
   - **GPIO pins**: Confirm hook switch pin (default: 22)
   - **Greeting**: Upload custom greeting or use default
   - **OpenAI** (optional): Add API key to enable AI features

### 4. Test Your Setup

1. Pick up the phone handset
2. Listen for the greeting and beep
3. Leave a test message
4. Hang up the phone
5. Check the web interface to see your recording
6. (If AI enabled) Watch as transcription and metadata appear

## AI Processing Setup

### Prerequisites
- OpenAI API key (get from [platform.openai.com/api-keys](https://platform.openai.com/api-keys))
- FFmpeg installed (`sudo apt-get install ffmpeg`)
- Internet connectivity

### Configuration

Edit `config.yaml` and set:

```yaml
openai_api_key: "sk-proj-your-key-here"
openai_auto_process: true              # Auto-process new recordings
openai_gpt_model: "gpt-4o-mini"        # Fast, cost-effective model
openai_language: "en"                  # Language code or "auto"
openai_compress_audio: true            # Saves 98% bandwidth
openai_processing_cooldown: 120        # Wait 2 min after recording
openai_allow_processing_during_call: false  # Process only when idle
```

### Recommended Settings by Pi Model

**Pi Zero / Zero 2** (Limited Resources):
```yaml
openai_processing_cooldown: 300        # 5 minutes
openai_allow_processing_during_call: false
openai_compress_audio: true
```

**Pi 3** (Moderate Resources):
```yaml
openai_processing_cooldown: 120        # 2 minutes (default)
openai_allow_processing_during_call: false
openai_compress_audio: true
```

**Pi 4 / Pi 5** (High Performance):
```yaml
openai_processing_cooldown: 30         # 30 seconds
openai_allow_processing_during_call: true
openai_compress_audio: true
```

### Cost Estimate
- **Whisper API**: $0.006 per minute
- **GPT-4o Mini**: ~$0.000135 per recording
- **Total**: ~$0.006 per minute of audio
- **Example**: 200 guests × 1 min average = ~$1.20

## Development

### Deployment Workflow

**Quick Mode** (for code changes):
```bash
./deploy.sh --quick blackbox
```
- Syncs files to Pi
- Auto-restarts services if templates/static changed
- Fast (~2-3 seconds)

**Full Deploy** (for dependencies/services):
```bash
./deploy.sh blackbox
```
- Installs system dependencies
- Installs Python packages
- Copies service files
- Restarts all services

See [Configuration Guide](docs/configuration.md) for detailed settings documentation. For moving the device between networks, see [WiFi Management](docs/wifi.md).

### Project Structure

```
rotary-phone-audio-guestbook/
├── src/                      # Core Python application
│   ├── audioGuestBook.py    # Main logic and phone event handling
│   ├── audioInterface.py    # ALSA audio wrapper
│   └── bootLed.py          # LED boot indicator
├── webserver/               # Flask web application
│   ├── server.py           # API endpoints and routes
│   ├── openai_processor.py # AI transcription and metadata
│   ├── job_queue.py        # Background processing queue
│   ├── metadata_manager.py # Thread-safe metadata storage
│   ├── connectivity_checker.py # Internet connectivity
│   ├── templates/          # Jinja2 HTML templates
│   └── static/             # CSS, JavaScript, assets
├── sounds/                  # Audio files (greetings, beeps)
├── recordings/             # Voice recordings (WAV + metadata)
├── docs/                   # Documentation
├── config.yaml             # Configuration file
├── deploy.sh              # Deployment script
└── *.service              # systemd service files
```

### Viewing Logs

```bash
# Main application logs
ssh admin@<pi-hostname> "sudo journalctl -u audioGuestBook.service -f"

# Web server logs
ssh admin@<pi-hostname> "sudo journalctl -u audioGuestBookWebServer.service -f"

# Filter for AI processing
ssh admin@<pi-hostname> "sudo journalctl -u audioGuestBook.service -f | grep -i openai"
```

## Troubleshooting

### Audio Issues
- **No sound**: Check `aplay -l` to verify audio device, update `alsa_hw_mapping` in config
- **Low volume**: Adjust with `amixer set Speaker 100%`
- **Poor quality**: Consider upgrading to lavalier mic (see [Hardware Guide](docs/hardware.md))

### Hook Switch Problems
- **Recording doesn't start**: Check GPIO wiring, try `invert_hook: true` in config
- **Wrong behavior**: Test with multimeter, adjust `hook_type` (NC vs NO)

### AI Processing Issues
- **Not processing**: Verify `openai_api_key` is set, check internet connection
- **Slow processing**: Enable `openai_compress_audio: true`, increase `openai_processing_cooldown`
- **API errors**: Check logs for rate limits, verify API key is valid

### Service Issues
```bash
# Check service status
sudo systemctl status audioGuestBook.service
sudo systemctl status audioGuestBookWebServer.service

# Restart services
sudo systemctl restart audioGuestBook.service audioGuestBookWebServer.service

# View recent errors
sudo journalctl -u audioGuestBook.service --no-pager -n 100
```

## API Endpoints

### Recordings Management
- `GET /api/recordings` - List recordings with AI metadata
- `GET /recordings/<filename>` - Stream audio file
- `GET /api/transcription/<filename>` - Get full transcription
- `POST /delete/<filename>` - Delete recording
- `POST /delete-recordings` - Bulk delete
- `POST /api/process-pending` - Manually process pending recordings

### System Control
- `GET /` - Recordings list (web UI)
- `GET /config` - Settings page
- `POST /config` - Update configuration
- `POST /reboot` - Reboot Raspberry Pi
- `POST /shutdown` - Shutdown Raspberry Pi

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test on actual hardware if possible
4. Submit a pull request with clear description

## Support

- **Documentation**: See [docs/](docs/) folder for detailed guides
- **Security**: See [docs/security.md](docs/security.md) for security best practices
- **Issues**: Report bugs via GitHub Issues
- **Questions**: Open a discussion on GitHub

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

*Attribution: inspired by [Nick Pourazima](https://github.com/nickpourazima)'s original [rotary-phone-audio-guestbook](https://github.com/nickpourazima/rotary-phone-audio-guestbook) (MIT).*
