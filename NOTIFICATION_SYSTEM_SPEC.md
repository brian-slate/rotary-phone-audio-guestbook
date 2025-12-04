# SMS/Email Notification System - Specification

## Overview

Add the ability to automatically send SMS and/or email notifications when new audio guestbook messages are recorded and processed. Notifications will include AI-generated transcriptions, metadata (speaker names, categories, sentiment), and links to listen to recordings.

## Use Cases

1. **Event Host Real-time Updates**: Receive notifications as guests leave messages during an event
2. **Remote Monitoring**: Know when the guestbook is being used without checking the web interface
3. **Message Sharing**: Automatically share transcriptions with family members or event participants
4. **Backup/Archive**: Email transcriptions for permanent record keeping

## Architecture

### Components

```
audioGuestBook.py (recording) 
    ↓ (saves recording)
openai_processor.py (AI processing)
    ↓ (transcription + metadata)
notification_manager.py (NEW)
    ↓ (formats & sends)
SMS Provider (Twilio) + Email Provider (SMTP/SendGrid)
```

### Integration Points

- **Trigger**: After successful OpenAI processing completion
- **Location**: Call from `openai_processor.py` after metadata saved
- **Async**: Non-blocking, queued notifications (don't delay recording)

## Service Providers

### SMS Options

#### Option 1: Twilio (Recommended)
**Pros**:
- Reliable, well-documented API
- Pay-as-you-go pricing (~$0.0079/SMS in US)
- Python SDK available (`twilio` package)
- Supports MMS (could send audio links)

**Cons**:
- Requires account setup and phone number purchase (~$1.15/month)
- Need credit card

**Setup**:
```bash
pip3 install twilio
```

**Config**:
```yaml
twilio_account_sid: "AC..."
twilio_auth_token: "..."
twilio_from_number: "+1234567890"
```

#### Option 2: AWS SNS
**Pros**:
- Integrated with AWS ecosystem
- Very low cost ($0.00645/SMS)

**Cons**:
- More complex setup
- Requires AWS account

### Email Options

#### Option 1: SMTP (Gmail, etc.)
**Pros**:
- Free for personal use
- Simple setup
- Built-in Python support (`smtplib`)

**Cons**:
- Gmail requires app-specific passwords
- Rate limits for free accounts
- May land in spam

**Setup**:
```yaml
smtp_server: "smtp.gmail.com"
smtp_port: 587
smtp_username: "your-email@gmail.com"
smtp_password: "app-specific-password"
```

#### Option 2: SendGrid
**Pros**:
- Free tier: 100 emails/day
- Better deliverability
- Analytics dashboard
- Python SDK

**Cons**:
- Requires account signup

**Setup**:
```bash
pip3 install sendgrid
```

#### Option 3: AWS SES
**Pros**:
- Very cheap ($0.10 per 1,000 emails)
- High reliability

**Cons**:
- Requires AWS account and verification
- Sandbox mode by default

## Configuration Schema

### New `config.yaml` Section

```yaml
# Notification Settings
notifications_enabled: true

# SMS Configuration (Twilio)
sms_enabled: false
twilio_account_sid: ""
twilio_auth_token: ""
twilio_from_number: ""
sms_recipients:
  - "+15551234567"
  - "+15559876543"

# Email Configuration (SMTP)
email_enabled: false
smtp_server: "smtp.gmail.com"
smtp_port: 587
smtp_use_tls: true
smtp_username: ""
smtp_password: ""
email_from: "guestbook@example.com"
email_from_name: "Audio Guestbook"
email_recipients:
  - "host@example.com"
  - "family@example.com"

# Notification Behavior
notification_send_transcription: true
notification_send_audio_link: true
notification_send_metadata: true
notification_include_category: true
notification_include_sentiment: true
notification_batch_mode: false  # If true, send digest instead of per-message
notification_batch_interval: 3600  # Seconds (1 hour)
notification_quiet_hours_start: "22:00"  # Optional: don't send between 10pm-8am
notification_quiet_hours_end: "08:00"
notification_max_transcription_length: 500  # Truncate long messages
```

## Message Format

### SMS Format (Character-limited)

```
🎙️ New Guestbook Message

From: John & Sarah
Category: Heartfelt 💖
Duration: 2:34

"We're so happy to be here celebrating..."

Listen: http://blackbox.local:8080/#msg123

---
Audio Guestbook
```

**Character count**: ~180-200 characters (fits in single SMS)

### Email Format (Rich HTML)

**Subject**: `🎙️ New Guestbook Message from [Speaker Names]`

**Body** (HTML):
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }
        .header { background: #4A90E2; color: white; padding: 20px; border-radius: 8px 8px 0 0; }
        .content { background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }
        .metadata { display: flex; gap: 15px; margin: 15px 0; }
        .badge { padding: 5px 10px; border-radius: 5px; font-size: 12px; }
        .category { background: #e3f2fd; color: #1976d2; }
        .transcription { background: white; padding: 15px; border-left: 4px solid #4A90E2; margin: 15px 0; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
        .button { background: #4A90E2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎙️ New Guestbook Message</h1>
    </div>
    <div class="content">
        <div class="metadata">
            <strong>From:</strong> John & Sarah
            <span class="badge category">💖 Heartfelt</span>
        </div>
        <div class="metadata">
            <span><strong>Duration:</strong> 2:34</span>
            <span><strong>Recorded:</strong> Dec 3, 2025 9:15 PM</span>
        </div>
        
        <h3>Transcription</h3>
        <div class="transcription">
            "We're so happy to be here celebrating with you both. We've known you since college and watching your love story unfold has been incredible..."
        </div>
        
        <a href="http://blackbox.local:8080/#msg123" class="button">🎧 Listen to Recording</a>
        
        <p style="color: #666; font-size: 12px; margin-top: 20px;">
            <strong>AI Confidence:</strong> 95%<br>
            <strong>Summary:</strong> Wedding congratulations from college friends
        </p>
    </div>
    <div class="footer">
        Sent by Audio Guestbook System<br>
        <a href="http://blackbox.local:8080">View All Messages</a>
    </div>
</body>
</html>
```

### Plain Text Email Fallback

```
🎙️ NEW GUESTBOOK MESSAGE
═══════════════════════════════════════

FROM: John & Sarah
CATEGORY: 💖 Heartfelt
DURATION: 2:34
RECORDED: Dec 3, 2025 9:15 PM

───────────────────────────────────────
TRANSCRIPTION
───────────────────────────────────────

"We're so happy to be here celebrating with you both. 
We've known you since college and watching your love 
story unfold has been incredible..."

───────────────────────────────────────

🎧 Listen: http://blackbox.local:8080/#msg123

AI Confidence: 95%
Summary: Wedding congratulations from college friends

═══════════════════════════════════════
Sent by Audio Guestbook System
View all messages: http://blackbox.local:8080
```

## Implementation Details

### File Structure

```
webserver/
├── notification_manager.py     # NEW: Core notification logic
├── sms_provider.py            # NEW: Twilio SMS wrapper
├── email_provider.py          # NEW: SMTP/SendGrid wrapper
├── notification_templates.py  # NEW: Message formatting
└── openai_processor.py        # MODIFY: Add notification trigger
```

### notification_manager.py

```python
class NotificationManager:
    def __init__(self, config):
        self.config = config
        self.sms_provider = SMSProvider(config) if config.get('sms_enabled') else None
        self.email_provider = EmailProvider(config) if config.get('email_enabled') else None
        self.queue = Queue()  # Async queue for reliability
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
    
    def notify_new_message(self, recording_data):
        """Queue notification for new processed message"""
        if not self.config.get('notifications_enabled'):
            return
        
        # Check quiet hours
        if self._is_quiet_hours():
            logger.info(f"Skipping notification during quiet hours")
            return
        
        self.queue.put({
            'type': 'new_message',
            'data': recording_data,
            'timestamp': datetime.now()
        })
    
    def _process_queue(self):
        """Background worker to send notifications"""
        while True:
            try:
                notification = self.queue.get(timeout=1)
                self._send_notification(notification)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Notification send failed: {e}")
    
    def _send_notification(self, notification):
        """Send via enabled channels"""
        data = notification['data']
        
        # Format messages
        sms_message = self._format_sms(data)
        email_html = self._format_email_html(data)
        email_text = self._format_email_text(data)
        
        # Send SMS
        if self.sms_provider:
            for recipient in self.config.get('sms_recipients', []):
                try:
                    self.sms_provider.send(recipient, sms_message)
                    logger.info(f"SMS sent to {recipient}")
                except Exception as e:
                    logger.error(f"SMS failed to {recipient}: {e}")
        
        # Send Email
        if self.email_provider:
            for recipient in self.config.get('email_recipients', []):
                try:
                    subject = self._format_email_subject(data)
                    self.email_provider.send(recipient, subject, email_html, email_text)
                    logger.info(f"Email sent to {recipient}")
                except Exception as e:
                    logger.error(f"Email failed to {recipient}: {e}")
```

### Integration with OpenAI Processor

**Modify `openai_processor.py`:**

```python
from notification_manager import NotificationManager

class OpenAIProcessor:
    def __init__(self, config, metadata_manager):
        # ... existing init ...
        self.notification_manager = NotificationManager(config)
    
    def _process_recording_internal(self, filename):
        # ... existing transcription and metadata extraction ...
        
        # Save metadata
        self.metadata_manager.save_metadata(filename, metadata)
        
        # NEW: Send notification
        if metadata.get('status') == 'completed':
            notification_data = {
                'filename': filename,
                'speakers': metadata.get('speakers', []),
                'category': metadata.get('category'),
                'transcription': metadata.get('transcription'),
                'summary': metadata.get('summary'),
                'duration': metadata.get('duration'),
                'timestamp': metadata.get('timestamp'),
                'confidence': metadata.get('confidence')
            }
            self.notification_manager.notify_new_message(notification_data)
```

### Error Handling & Reliability

1. **Queue-based delivery**: Notifications don't block main recording/processing
2. **Retry logic**: Failed notifications retry with exponential backoff
3. **Graceful degradation**: If SMS fails, email still sends (and vice versa)
4. **Logging**: All notification attempts logged for debugging
5. **Rate limiting**: Prevent notification spam if many messages recorded quickly

## Security Considerations

### API Key Storage

**Current approach** (config.yaml):
- Simple but keys stored in plain text
- Acceptable for local-only deployment

**Future enhancement**:
- Environment variables
- Encrypted config section
- Secret management (AWS Secrets Manager, Vault)

### Privacy

- **Transcriptions contain personal data**: Ensure recipients are authorized
- **No external storage**: Notifications ephemeral (not stored by system)
- **Opt-out mechanism**: Easy to disable via config
- **GDPR consideration**: If used in EU, ensure compliance

### Network Security

- **TLS for SMTP**: Always use `smtp_use_tls: true`
- **HTTPS for links**: If exposing web UI publicly, use HTTPS
- **Local network only**: Default setup assumes blackbox.local not internet-accessible

## Testing Strategy

### Unit Tests

```python
# test_notification_manager.py
def test_format_sms_within_character_limit():
    assert len(formatted_message) <= 160

def test_email_html_valid():
    assert '<html>' in formatted_email

def test_quiet_hours_respected():
    # Set time to 11pm
    assert notification_manager._is_quiet_hours() == True
```

### Integration Tests

1. **Mock providers**: Test without actual SMS/email sending
2. **Test accounts**: Use Twilio test credentials
3. **Local SMTP**: Use MailHog or similar for email testing

### Manual Testing Checklist

- [ ] SMS received on phone
- [ ] Email received in inbox (not spam)
- [ ] Links in notifications work
- [ ] Formatting renders correctly on mobile
- [ ] Multiple recipients all receive notifications
- [ ] Quiet hours prevent sending
- [ ] Graceful failure if provider unavailable
- [ ] No impact on recording performance

## Deployment Steps

### Phase 1: Development & Testing (Local)

```bash
# Install dependencies
pip3 install twilio sendgrid

# Update config.yaml with test credentials
vim config.yaml

# Test locally (mock recording)
python3 webserver/notification_manager.py --test

# Deploy to Pi
./deploy.sh blackbox
```

### Phase 2: Staging (Pi with Test Providers)

```bash
# Use Twilio test credentials
# Use test email addresses

# Deploy
./deploy.sh blackbox

# Make test recording
# Verify notifications received

# Check logs
ssh admin@blackbox "sudo journalctl -u audioGuestBook.service | grep -i notification"
```

### Phase 3: Production

```bash
# Update config with production credentials
# Set real recipient phone numbers/emails

# Deploy
./deploy.sh blackbox

# Monitor during real event
```

## Configuration Examples

### Minimal Setup (SMS only, Twilio)

```yaml
notifications_enabled: true
sms_enabled: true
twilio_account_sid: "AC1234567890abcdef"
twilio_auth_token: "your_auth_token"
twilio_from_number: "+15551234567"
sms_recipients:
  - "+15559876543"
notification_send_transcription: true
```

### Full Setup (SMS + Email)

```yaml
notifications_enabled: true

sms_enabled: true
twilio_account_sid: "AC1234567890abcdef"
twilio_auth_token: "your_auth_token"
twilio_from_number: "+15551234567"
sms_recipients:
  - "+15559876543"

email_enabled: true
smtp_server: "smtp.gmail.com"
smtp_port: 587
smtp_use_tls: true
smtp_username: "guestbook@gmail.com"
smtp_password: "app_password_here"
email_from: "guestbook@gmail.com"
email_from_name: "Wedding Guestbook"
email_recipients:
  - "bride@example.com"
  - "groom@example.com"

notification_send_transcription: true
notification_send_audio_link: true
notification_send_metadata: true
notification_quiet_hours_start: "22:00"
notification_quiet_hours_end: "08:00"
```

### Batch Mode (Digest Emails)

```yaml
notifications_enabled: true
email_enabled: true
notification_batch_mode: true
notification_batch_interval: 3600  # Send digest every hour
# ... rest of email config ...
```

## Cost Estimates

### Twilio SMS (US)
- **Per message**: $0.0079
- **100 messages/event**: $0.79
- **Phone number rental**: $1.15/month
- **Total for single event**: ~$2

### SendGrid Email
- **Free tier**: 100 emails/day (sufficient for most events)
- **Paid tier**: $19.95/month (40,000 emails)

### SMTP (Gmail)
- **Free**: For personal use
- **Limits**: ~500 emails/day

## Performance Impact

### Pi Zero W Considerations

- **Async queue**: Notifications don't block recording
- **Lightweight libraries**: Twilio/SMTP minimal overhead
- **Network I/O**: Brief spikes during send (< 1 second)
- **Expected impact**: Negligible (already doing OpenAI API calls)

### Recommendations

- Enable notifications **after** verifying OpenAI processing is stable
- Monitor system resources during first event
- Have fallback plan (disable notifications if issues)

## Future Enhancements

### Phase 2 Features

1. **Webhook support**: Allow external services to subscribe
2. **Custom templates**: User-defined message formats
3. **Notification preferences per recipient**: Some get SMS, others email
4. **Message filtering**: Only notify for certain categories
5. **Reply-to-recording**: SMS back to rate/comment on messages
6. **MMS with audio**: Send actual audio file via MMS (if < 500KB)
7. **Push notifications**: Mobile app integration

### Advanced Features

1. **Two-way SMS**: Guest can text to be added to guestbook
2. **Voice-to-SMS bridging**: Call a number to leave message remotely
3. **Social sharing**: Auto-post highlights to social media
4. **Analytics dashboard**: Notification delivery stats

## Dependencies

### New Python Packages

```bash
# SMS (Twilio)
pip3 install twilio

# Email (SendGrid - optional)
pip3 install sendgrid

# Built-in (no install needed)
# - smtplib (SMTP)
# - email.mime (email formatting)
```

### Update requirements.txt

```
# ... existing packages ...
twilio>=8.0.0
sendgrid>=6.9.0  # Optional
```

## Documentation Updates

After implementation, update:

- **README.md**: Add notification setup section
- **WARP.md**: Add notification configuration and troubleshooting
- **config.yaml**: Add commented examples
- **Web UI**: Add notification settings page

## Success Metrics

- Notification delivery rate > 99%
- No impact on recording quality
- Latency < 5 seconds from recording finish to notification
- Zero notification-related crashes
- Positive user feedback on usefulness

## Rollback Plan

If issues arise:

```yaml
# Emergency disable
notifications_enabled: false
```

```bash
# Restart service
ssh admin@blackbox "sudo systemctl restart audioGuestBook.service"
```

System returns to pre-notification behavior immediately.
