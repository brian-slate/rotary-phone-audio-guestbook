# OpenAI Integration Implementation Summary

## Overview
Added OpenAI Whisper and GPT-4o Mini integration to automatically extract metadata (transcriptions, speaker names, emotional categories, summaries) from audio recordings.

## Files Created
1. **webserver/metadata_manager.py** - Thread-safe JSON-based metadata storage
2. **webserver/connectivity_checker.py** - Internet connectivity checking with caching
3. **webserver/openai_processor.py** - OpenAI Whisper + GPT-4o Mini integration
4. **webserver/job_queue.py** - Background processing queue with idle-time processing

## Files Modified
1. **config.yaml** - Added OpenAI configuration settings
2. **src/audioGuestBook.py** - Integrated AI components into recording flow
3. **webserver/server.py** - Updated API to return metadata, added new endpoints
4. **webserver/static/js/recordings.js** - Updated frontend to display AI metadata
5. **webserver/templates/index.html** - Added Speakers and Category columns

## Key Features
- **Automatic Processing**: Recordings are automatically queued for AI processing after being saved
- **Idle-Time Processing**: AI processing only happens when phone is idle (not during active calls)
- **Offline Resilience**: Recordings marked as "pending" if no internet, can be processed later
- **Metadata Display**: Shows AI-generated titles, speaker names, categories with colored badges
- **Transcription Modal**: Click on message titles to view full transcriptions
- **Processing Status**: Visual indicators show processing status (pending, processing, completed)
- **Auto-Refresh**: Frontend automatically polls for updates while recordings are processing

## Configuration
Added to `config.yaml`:
```yaml
# OpenAI AI Processing Configuration
openai_enabled: false              # Master toggle for AI processing
openai_auto_process: true          # Auto-process new recordings
openai_api_key: ""                # OpenAI API key (starts with sk-)
openai_gpt_model: "gpt-4o-mini"   # Model for metadata extraction
openai_language: "en"              # Language code (en, es, fr, etc., or "auto")
openai_min_duration: 5             # Skip recordings shorter than N seconds
```

## API Endpoints Added
1. **GET /api/recordings** - Now returns metadata for each recording
2. **GET /api/transcription/<filename>** - Get full transcription for a recording
3. **POST /api/process-pending** - Manually trigger processing of unprocessed recordings

## Next Steps to Use
1. Install dependencies: `pip install openai requests`
2. Get OpenAI API key from https://platform.openai.com/api-keys
3. Update `config.yaml` with your API key and set `openai_enabled: true`
4. Restart services:
   ```bash
   sudo systemctl restart audioGuestBook.service
   sudo systemctl restart gunicorn
   ```

## Metadata Schema
Recordings metadata is stored in `recordings_metadata.json`:
```json
{
  "version": "1.0",
  "recordings": {
    "2024-12-01T15:30:45.wav": {
      "filename": "2024-12-01T15:30:45.wav",
      "created_at": "2024-12-01T15:30:45",
      "duration_seconds": 180.5,
      "file_size_bytes": 31752000,
      "ai_metadata": {
        "transcription": "Full text of what was said...",
        "speaker_names": ["John", "Sarah"],
        "category": "joyful",
        "summary": "John and Sarah's wedding wishes",
        "processing_status": "completed",
        "processed_at": "2024-12-01T15:32:15",
        "confidence": 0.95
      }
    }
  }
}
```

## Categories
- joyful - Happy, celebratory messages
- heartfelt - Emotional, sincere well-wishes
- humorous - Funny, lighthearted jokes
- nostalgic - Memories and reminiscing
- advice - Life advice or wisdom
- blessing - Religious or spiritual blessings
- toast - Celebratory toasts or cheers
- gratitude - Thank you messages
- apology - Unable to attend messages
- other - Miscellaneous

## Cost Estimate
Based on OpenAI pricing:
- Whisper API: $0.006 per minute
- GPT-4o Mini: ~$0.000135 per recording
- **Total per 1-minute recording: ~$0.006**
- 200-person wedding event: ~$1.23

## Enhancements

See `OPENAI_ENHANCEMENTS.md` for detailed information on:
1. **Audio Compression** (98% bandwidth reduction via MP3 conversion)
2. **Smart Processing Timing** (cooldown periods + flexible idle checking)
3. **Retry Logic** (automatic retries with exponential backoff)
4. **Performance Optimization** (configurable for different Pi models)

Key features:
- Compress WAV to MP3 before upload (saves 90%+ bandwidth)
- Wait for cooldown period after last recording
- Retry failed API calls automatically
- Configurable processing timing based on Pi capabilities

## Graceful Degradation
The system works without OpenAI integration enabled:
- If `openai_enabled: false`, recordings work normally without AI processing
- If OpenAI library not installed, system logs warning but continues to function
- If no API key configured, AI processing is skipped
- If no internet, recordings are marked as "pending" for later processing
- If FFmpeg not installed, falls back to uncompressed WAV upload
