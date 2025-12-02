# AI Metadata Extraction Implementation Plan (OpenAI Version)

## Overview
Add OpenAI Whisper and GPT-4o Mini integration to automatically extract metadata (speaker names, emotional category, summary title) from audio recordings. The system will:
- Use OpenAI Whisper API for transcription
- Use GPT-4o Mini for metadata extraction
- Store metadata in local JSON file
- Process only when phone is idle (not during active calls)
- Gracefully handle offline scenarios
- Provide manual processing controls via config UI

## Why OpenAI Instead of AWS?
- **75% cheaper**: $1.23 vs $5.00 for 200 one-minute recordings
- **Much simpler**: No S3, IAM, or AWS infrastructure needed
- **Faster**: 7-12 seconds vs 40-100 seconds per recording
- **Single API key**: No complex credential management
- **No S3 required**: Direct file upload to OpenAI

## Questions to Address Before Implementation
1. **Language Support**: Default to English or support multiple languages?
2. **Processing Delay**: Add delay before processing to allow deleting bad recordings?
3. **Minimum Duration**: Skip processing for recordings shorter than X seconds (e.g., 5 seconds)?

## Architecture

### Current State
- Recordings saved as WAV files with ISO timestamp filenames
- Flask webserver serves files from `recordings_path` directory
- No metadata storage beyond filesystem
- Frontend displays filenames in table

### New Components
1. **Metadata Storage**: `recordings_metadata.json` in recordings directory
2. **OpenAI Processor Module**: `webserver/openai_processor.py`
3. **Background Worker**: Threading-based job queue with idle-time processing
4. **Internet Checker**: Connectivity validation
5. **Metadata Manager**: Thread-safe JSON file handler
6. **UI Updates**: Display AI-extracted metadata
7. **Settings Controls**: Enable/disable + manual processing + tooltips

## Cost Analysis

### OpenAI Whisper API Pricing
- **Price**: $0.006 per minute of audio
- **1-minute recording**: $0.006
- **3-minute recording**: $0.018
- **Features**: Multilingual, timestamps, high accuracy

### OpenAI GPT-4o Mini Pricing
- **Input**: $0.150 per 1M tokens (~$0.00015 per 1K tokens)
- **Output**: $0.600 per 1M tokens (~$0.0006 per 1K tokens)
- **Average usage per recording**:
  - Input: ~500 tokens (transcription + prompt) = $0.000075
  - Output: ~100 tokens (JSON response) = $0.00006
  - **Total per recording**: ~$0.000135
- **Speed**: 2-3 seconds
- **Model ID**: `gpt-4o-mini`

### Total Cost Estimates

**Per Recording:**
- 1-minute: $0.006 (Whisper) + $0.000135 (GPT) = **~$0.006**
- 3-minute: $0.018 (Whisper) + $0.000135 (GPT) = **~$0.018**

**Event Examples (1-minute average messages):**
- 50-person wedding: **$0.30**
- 100-person wedding: **$0.61**
- 200-person wedding: **$1.23**

**Event Examples (3-minute average messages):**
- 50-person wedding: **$0.91**
- 100-person wedding: **$1.82**
- 200-person wedding: **$3.64**

### Cost Comparison: OpenAI vs AWS

| Metric | AWS Solution | OpenAI Solution |
|--------|--------------|-----------------|
| **Cost (200 msgs, 1-min)** | $5.00 | **$1.23** ✅ |
| **Setup Complexity** | High (IAM, S3, regions) | **Low (API key only)** ✅ |
| **Processing Time** | 40-100 sec | **7-12 sec** ✅ |
| **Infrastructure** | S3 bucket required | **None** ✅ |
| **Code Complexity** | High (async jobs, polling) | **Low (sync calls)** ✅ |

### Cost Optimization Strategies

1. **Skip Short Recordings**:
   - Don't process recordings < 5 seconds (likely misdials/noise)
   - Saves ~$0.03 per skipped recording

2. **Process Only When Idle**:
   - Avoids interference with active calls
   - Spreads CPU/network load

3. **Efficient Prompting**:
   - Keep prompts concise to minimize input tokens
   - Request JSON-only output (no explanations)
   - Use `response_format={"type": "json_object"}` for guaranteed JSON

4. **Cache Transcriptions**:
   - Never re-transcribe the same file
   - Store in metadata JSON permanently

5. **Batch Processing** (Future):
   - Could batch multiple transcriptions in single GPT call
   - Marginal savings since GPT cost is already negligible

### Processing Time Estimate
- **Whisper API**: 5-10 seconds (synchronous)
- **GPT-4o Mini**: 2-3 seconds
- **Network overhead**: 1-2 seconds
- **Total**: ~7-12 seconds per recording
- Runs in background without blocking new recordings

## Implementation Steps

### Phase 1: Setup

#### 1.1 Install Dependencies

**Add to `requirements.txt` or `pyproject.toml`**:
```
openai>=1.0.0
```

**Install on Raspberry Pi**:
```bash
pip install openai
```

### Phase 2: Backend Implementation

#### 2.1 Metadata Storage Schema

**File**: `recordings_metadata.json` (stored in `recordings_path` directory)

**Schema**:
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

**Processing Status Values**:
- `pending`: Not yet processed (no internet or auto-process disabled)
- `processing`: Currently being processed
- `completed`: Successfully processed
- `failed`: Processing failed
- `skipped`: Skipped (disabled or too short)
- `null`: Legacy recordings (pre-AI feature)

**Message Categories**:
- `joyful`: Happy, celebratory messages
- `heartfelt`: Emotional, sincere well-wishes
- `humorous`: Funny, lighthearted jokes
- `nostalgic`: Memories and reminiscing
- `advice`: Life advice or wisdom
- `blessing`: Religious or spiritual blessings
- `toast`: Celebratory toasts or cheers
- `gratitude`: Thank you messages
- `apology`: Unable to attend messages
- `other`: Miscellaneous

#### 2.2 Create Metadata Manager

**File**: `webserver/metadata_manager.py`

**Purpose**: Thread-safe JSON file read/write operations

**Key Methods**:
- `get_metadata(filename)`: Get metadata for single recording
- `update_metadata(filename, metadata)`: Update/create metadata entry
- `get_all_recordings()`: Get all recordings with metadata merged
- `get_unprocessed_recordings()`: Get recordings needing AI processing
- `initialize_recording(filename, file_size)`: Create initial entry
- `mark_as_processing(filename)`: Set status to processing
- `mark_as_completed(filename, ai_data)`: Set status to completed with data
- `mark_as_failed(filename, error)`: Set status to failed

**Thread Safety**: Use `threading.Lock()` for all file access

**Implementation Notes**:
- Load entire JSON file, modify in memory, write back
- Handle missing files gracefully (create if doesn't exist)
- Merge with filesystem listing (show all WAV files even if not in JSON)

#### 2.3 Create Internet Connectivity Checker

**File**: `webserver/connectivity_checker.py`

**Purpose**: Check if internet is available before attempting API calls

**Implementation**:
```python
import requests
import time
import logging

logger = logging.getLogger(__name__)

class ConnectivityChecker:
    def __init__(self, cache_duration=60):
        self.cache_duration = cache_duration
        self.last_check_time = 0
        self.last_result = False
    
    def check_internet_available(self):
        """Check if internet is available (cached for 60 seconds)"""
        current_time = time.time()
        
        # Return cached result if recent
        if current_time - self.last_check_time < self.cache_duration:
            return self.last_result
        
        # Try to reach OpenAI API
        try:
            response = requests.head(
                "https://api.openai.com",
                timeout=3
            )
            self.last_result = response.status_code < 500
        except requests.RequestException:
            self.last_result = False
        
        self.last_check_time = current_time
        logger.info(f"Internet check: {'available' if self.last_result else 'unavailable'}")
        return self.last_result
```

**Caching**: Result cached for 60 seconds to avoid excessive checks

#### 2.4 Create OpenAI Processor Module

**File**: `webserver/openai_processor.py`

**Purpose**: Handle all OpenAI API interactions (Whisper + GPT)

**Configuration from config.yaml**:
```python
import openai
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, config):
        self.enabled = config.get('openai_enabled', False)
        self.gpt_model = config.get('openai_gpt_model', 'gpt-4o-mini')
        self.language = config.get('openai_language', 'en')
        self.min_duration = config.get('openai_min_duration', 5)
        
        if self.enabled:
            openai.api_key = config.get('openai_api_key', '')
            if not openai.api_key:
                logger.warning("OpenAI API key not configured")
                self.enabled = False
```

**Main Processing Method**:
```python
def process_recording(self, audio_file_path, filename):
    """Process a single recording through Whisper + GPT pipeline"""
    if not self.enabled:
        raise ValueError("OpenAI processing not enabled")
    
    try:
        # 1. Transcribe with Whisper API
        logger.info(f"Transcribing {filename} with Whisper...")
        transcription = self._transcribe_with_whisper(audio_file_path)
        
        if not transcription or len(transcription.strip()) < 10:
            logger.warning(f"Transcription too short or empty for {filename}")
            return None
        
        # 2. Extract metadata with GPT
        logger.info(f"Extracting metadata for {filename} with GPT...")
        metadata = self._extract_metadata_with_gpt(transcription)
        
        return {
            'transcription': transcription,
            'speaker_names': metadata.get('names', []),
            'category': metadata.get('category', 'other'),
            'summary': metadata.get('summary', filename),
            'confidence': metadata.get('confidence', 0.5)
        }
    
    except Exception as e:
        logger.error(f"Processing failed for {filename}: {e}")
        raise
```

**Whisper Transcription**:
```python
def _transcribe_with_whisper(self, audio_file_path):
    """Transcribe audio with OpenAI Whisper API"""
    with open(audio_file_path, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=self.language if self.language != 'auto' else None,
            response_format="text"
        )
    return transcript
```

**GPT Metadata Extraction**:
```python
def _extract_metadata_with_gpt(self, transcription):
    """Use GPT-4o Mini to extract metadata from transcription"""
    prompt = f"""Analyze this wedding/event guestbook message and extract:

1. Speaker names mentioned (first names only, if identifiable)
2. Emotional category (choose one: joyful, heartfelt, humorous, nostalgic, advice, blessing, toast, gratitude, apology, other)
3. A brief 4-7 word title summarizing the message
4. Confidence score (0.0-1.0) based on clarity

Transcription:
{transcription}

Respond ONLY with valid JSON in this exact format:
{{
  "names": ["Name1", "Name2"],
  "category": "joyful",
  "summary": "Brief message title here",
  "confidence": 0.95
}}"""
    
    response = openai.chat.completions.create(
        model=self.gpt_model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,  # Lower = more consistent
        max_tokens=200,
        response_format={"type": "json_object"}  # Ensures JSON output
    )
    
    content = response.choices[0].message.content
    metadata = json.loads(content)
    return metadata
```

**Key Features**:
- Synchronous API calls (no polling needed)
- Automatic JSON response formatting
- Error handling for API failures
- Configurable language support
- Minimum duration filtering

#### 2.5 Create Background Job Queue with Idle-Time Processing

**File**: `webserver/job_queue.py`

**Purpose**: Process recordings in background, only when phone is idle

**Implementation**:
```python
import threading
import queue
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ProcessingQueue:
    def __init__(self, processor, metadata_manager, connectivity_checker, 
                 phone_state_checker, config):
        self.queue = queue.Queue()
        self.processor = processor
        self.metadata_manager = metadata_manager
        self.connectivity_checker = connectivity_checker
        self.phone_state_checker = phone_state_checker  # Function to check if phone is idle
        self.config = config
        self.running = False
        self.worker_thread = None
    
    def start(self):
        """Start background worker thread"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name="AI-ProcessingQueue"
            )
            self.worker_thread.start()
            logger.info("AI processing queue started")
    
    def stop(self):
        """Stop background worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        logger.info("AI processing queue stopped")
    
    def enqueue(self, audio_file_path, filename):
        """Add recording to processing queue"""
        if self.config.get('openai_auto_process', True):
            self.queue.put((audio_file_path, filename))
            logger.info(f"Queued {filename} for AI processing")
        else:
            logger.info(f"Auto-process disabled, skipping {filename}")
            self.metadata_manager.update_metadata(filename, {
                'ai_metadata': {'processing_status': 'skipped'}
            })
```

**Worker Loop with Idle-Time Processing**:
```python
def _worker(self):
    """Background worker - processes queue only when phone is idle"""
    while self.running:
        try:
            # Non-blocking get with timeout
            try:
                audio_file_path, filename = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            # CRITICAL: Check if phone is IDLE before processing
            while self.phone_state_checker() and self.running:
                logger.debug("Phone active, waiting to process...")
                time.sleep(5)  # Check every 5 seconds
            
            if not self.running:
                break
            
            # Check if OpenAI is enabled
            if not self.config.get('openai_enabled', False):
                logger.info("OpenAI processing disabled, marking as skipped")
                self.metadata_manager.update_metadata(filename, {
                    'ai_metadata': {'processing_status': 'skipped'}
                })
                continue
            
            # Check internet connectivity
            if not self.connectivity_checker.check_internet_available():
                logger.warning("No internet, marking as pending")
                self.metadata_manager.update_metadata(filename, {
                    'ai_metadata': {'processing_status': 'pending'}
                })
                continue
            
            # Check minimum duration (optional)
            file_path = Path(audio_file_path)
            if not file_path.exists():
                logger.error(f"File not found: {audio_file_path}")
                continue
            
            # Mark as processing
            self.metadata_manager.mark_as_processing(filename)
            
            # PROCESS THE RECORDING
            logger.info(f"Processing {filename}...")
            result = self.processor.process_recording(audio_file_path, filename)
            
            if result:
                # Update metadata with results
                self.metadata_manager.mark_as_completed(filename, result)
                logger.info(f"Successfully processed {filename}")
            else:
                self.metadata_manager.mark_as_failed(
                    filename,
                    "Transcription empty or too short"
                )
        
        except Exception as e:
            logger.error(f"Processing error for {filename}: {e}")
            self.metadata_manager.mark_as_failed(filename, str(e))
        
        finally:
            self.queue.task_done()
```

**Key Features**:
- Only processes when phone is idle (checks `CurrentEvent.NONE`)
- Waits in 5-second intervals during active calls
- Checks internet before processing
- Graceful failure handling
- Thread-safe queue operations

#### 2.6 Update audioGuestBook.py Integration

**In `__init__` method** (after audio_interface setup):
```python
# Import AI processing components
from job_queue import ProcessingQueue
from openai_processor import AudioProcessor
from metadata_manager import MetadataManager
from connectivity_checker import ConnectivityChecker

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
    is_phone_active,  # Pass the state checker
    self.config
)
self.processing_queue.start()
logger.info("AI processing queue initialized")
```

**In `start_recording` method**:
```python
def start_recording(self, output_file: str):
    self.current_recording_path = output_file  # Store for later
    self.audio_interface.start_recording(output_file)
    logger.info(f"Recording started: {output_file}")
    # ... rest of existing code
```

**In `on_hook` method** (after recording saved):
```python
def on_hook(self):
    if self.current_event == CurrentEvent.HOOK:
        logger.info("Phone on hook. Ending call and saving recording.")
        
        # Stop recording and playback
        self.stop_recording_and_playback()
        
        # Queue for AI processing if we have a recording path
        if hasattr(self, 'current_recording_path'):
            file_path = Path(self.current_recording_path)
            
            if file_path.exists():
                # Initialize metadata entry
                self.metadata_manager.initialize_recording(
                    file_path.name,
                    file_path.stat().st_size
                )
                
                # Queue for AI processing (will process when idle)
                self.processing_queue.enqueue(
                    str(file_path),
                    file_path.name
                )
                logger.info(f"Queued {file_path.name} for AI processing")
        
        # Stop LED animation and return to ready state
        self.led_stop_animation()
        
        # Reset state
        self.current_event = CurrentEvent.NONE
        logger.info("Ready for next recording")
```

**In `run` method** (cleanup on shutdown):
```python
def run(self):
    logger.info("System ready. Lift the handset to start.")
    try:
        pause()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Stop processing queue
        if hasattr(self, 'processing_queue'):
            self.processing_queue.stop()
        # Cleanup LEDs
        self.led_cleanup()
```

#### 2.7 Update config.yaml Schema

**Add OpenAI configuration section**:
```yaml
# ... existing config ...

# OpenAI AI Processing Configuration
openai_enabled: false              # Master toggle for AI processing
openai_auto_process: true          # Auto-process new recordings
openai_api_key: ""                # OpenAI API key (starts with sk-)
openai_gpt_model: "gpt-4o-mini"   # Model for metadata extraction
openai_language: "en"              # Language code (en, es, fr, etc., or "auto")
openai_min_duration: 5             # Skip recordings shorter than N seconds
```

**Configuration Tooltips** (for UI):
- `openai_enabled`: "Enable AI-powered transcription and metadata extraction for recordings"
- `openai_auto_process`: "Automatically process new recordings when internet is available and phone is idle"
- `openai_api_key`: "Your OpenAI API key (get one at platform.openai.com/api-keys)"
- `openai_gpt_model`: "AI model for metadata extraction (gpt-4o-mini recommended for cost/speed)"
- `openai_language`: "Primary language of recordings (en=English, es=Spanish, etc. Use 'auto' for detection)"
- `openai_min_duration`: "Skip processing very short recordings (likely misdials or noise)"

#### 2.8 Update server.py API Endpoints

**Modified GET `/api/recordings`** - Return metadata:
```python
@app.route("/api/recordings")
def get_recordings():
    """Return recordings with AI metadata"""
    try:
        # Import here to avoid circular imports
        from metadata_manager import MetadataManager
        metadata_mgr = MetadataManager(recordings_path)
        
        # Get all recordings with metadata
        recordings = metadata_mgr.get_all_recordings()
        
        # Return with metadata
        return jsonify([
            {
                'filename': rec['filename'],
                'title': rec.get('ai_metadata', {}).get('summary') or rec['filename'],
                'speaker_names': rec.get('ai_metadata', {}).get('speaker_names', []),
                'category': rec.get('ai_metadata', {}).get('category'),
                'transcription': rec.get('ai_metadata', {}).get('transcription'),
                'processing_status': rec.get('ai_metadata', {}).get('processing_status'),
                'confidence': rec.get('ai_metadata', {}).get('confidence'),
                'created_at': rec.get('created_at'),
                'file_size': rec.get('file_size_bytes')
            }
            for rec in recordings
        ])
    except Exception as e:
        logger.error(f"Error getting recordings: {e}")
        return jsonify({"error": str(e)}), 500
```

**New POST `/api/process-pending`** - Manual processing:
```python
@app.route("/api/process-pending", methods=["POST"])
def process_pending_recordings():
    """Manually trigger processing of all unprocessed recordings"""
    try:
        from metadata_manager import MetadataManager
        
        # Get reference to processing queue (needs to be accessible)
        # This assumes processing_queue is stored in app context or global
        metadata_mgr = MetadataManager(recordings_path)
        unprocessed = metadata_mgr.get_unprocessed_recordings()
        
        count = 0
        for rec in unprocessed:
            file_path = recordings_path / rec['filename']
            if file_path.exists():
                # Add to processing queue
                # Note: Need access to processing_queue instance
                processing_queue.enqueue(str(file_path), rec['filename'])
                count += 1
        
        return jsonify({
            'success': True,
            'message': f'Queued {count} recording(s) for processing',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error processing pending recordings: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
```

**New GET `/api/transcription/<filename>`** - Get transcription:
```python
@app.route("/api/transcription/<filename>")
def get_transcription(filename):
    """Get full transcription for a recording"""
    try:
        from metadata_manager import MetadataManager
        metadata_mgr = MetadataManager(recordings_path)
        metadata = metadata_mgr.get_metadata(filename)
        
        if not metadata or 'ai_metadata' not in metadata:
            return jsonify({
                'transcription': None,
                'status': 'not_processed'
            })
        
        return jsonify({
            'transcription': metadata['ai_metadata'].get('transcription'),
            'status': metadata['ai_metadata'].get('processing_status'),
            'speaker_names': metadata['ai_metadata'].get('speaker_names', []),
            'category': metadata['ai_metadata'].get('category'),
            'confidence': metadata['ai_metadata'].get('confidence')
        })
    except Exception as e:
        logger.error(f"Error getting transcription: {e}")
        return jsonify({"error": str(e)}), 500
```

**Note**: The processing_queue needs to be accessible to the Flask app. Consider:
1. Storing it in `app.config` during initialization
2. Using a global variable (not ideal but simplest)
3. Creating a singleton pattern

### Phase 3: Frontend Implementation

#### 3.1 Update index.html Template

**Modify table header** (replace line 26):
```html
<th class="p-3 text-left font-semibold">Message</th>  <!-- Was "Filename" -->
<th class="p-3 text-left font-semibold">Speakers</th>  <!-- New column -->
<th class="p-3 text-left font-semibold">Category</th>  <!-- New column -->
<th class="p-3 text-left font-semibold">Audio</th>
<th class="p-3 text-left font-semibold">Date</th>
<th class="p-3 w-24 text-right font-semibold">Actions</th>
```

#### 3.2 Update recordings.js

**Modify `createRecordingItem` function** to display AI metadata:
```javascript
function createRecordingItem(recording) {
  const row = document.createElement("tr");
  row.className = "recording-item border-b border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors duration-200";
  
  // Use AI summary as title, fallback to filename
  const displayTitle = recording.title || recording.filename;
  const isProcessed = recording.processing_status === 'completed';
  const isProcessing = recording.processing_status === 'processing';
  const isPending = recording.processing_status === 'pending';
  
  // Format speaker names
  const speakerDisplay = recording.speaker_names && recording.speaker_names.length > 0
    ? recording.speaker_names.join(', ')
    : '-';
  
  // Category badge with color coding
  const categoryColors = {
    joyful: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    heartfelt: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    humorous: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    nostalgic: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    advice: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    blessing: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
    toast: 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200',
    gratitude: 'bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200',
    apology: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
    other: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
  };
  
  const categoryClass = categoryColors[recording.category] || 'bg-gray-100 text-gray-800';
  const categoryBadge = recording.category
    ? `<span class="px-2 py-1 rounded text-xs font-semibold ${categoryClass}">${recording.category}</span>`
    : '-';
  
  // Processing status indicator
  let statusIndicator = '';
  if (isProcessing) {
    statusIndicator = '<i class="fas fa-spinner fa-spin ml-2 text-blue-500" title="Processing..."></i>';
  } else if (isPending) {
    statusIndicator = '<i class="fas fa-clock ml-2 text-gray-400" title="Pending processing"></i>';
  } else if (isProcessed) {
    statusIndicator = '<i class="fas fa-check-circle ml-2 text-green-500" title="Processed"></i>';
  }
  
  const dateTime = parseDateTime(recording.filename);
  const formattedDate = moment(dateTime).format("MMMM D, YYYY [at] h:mm A");
  
  const hue = Math.floor(Math.random() * 360);
  const iconColor = `hsl(${hue}, 70%, 80%)`;
  
  row.innerHTML = `
    <td class="p-2 text-center">
      <input type="checkbox" class="recording-checkbox w-4 h-4" data-id="${recording.filename}">
    </td>
    <td class="p-2">
      <div class="flex items-center">
        <div class="w-8 h-8 rounded-full flex items-center justify-center mr-3" 
             style="background-color: ${iconColor}">
          <i class="fas fa-microphone text-white"></i>
        </div>
        <div>
          <span class="recording-name font-semibold cursor-pointer hover:text-blue-600" 
                data-filename="${recording.filename}"
                title="Click to view full transcription">
            ${displayTitle}
          </span>
          ${statusIndicator}
        </div>
      </div>
    </td>
    <td class="p-2 text-sm text-gray-700 dark:text-gray-300">${speakerDisplay}</td>
    <td class="p-2">${categoryBadge}</td>
    <td class="p-2">
      <audio class="audio-player" src="/recordings/${recording.filename}"></audio>
    </td>
    <td class="p-2 recording-date text-sm text-gray-600 dark:text-gray-400">
      ${formattedDate}
    </td>
    <td class="p-2">
      <button class="delete-button bg-red-500 hover:bg-red-600 text-white 
                     rounded-md px-3 py-2 flex items-center transition-colors duration-200 shadow-sm">
        <i class="fas fa-times mr-1"></i>
        <span class="hidden sm:inline">Delete</span>
      </button>
    </td>
  `;
  
  // Add click handler to show transcription modal
  const nameSpan = row.querySelector('.recording-name');
  nameSpan.addEventListener('click', (e) => {
    e.stopPropagation();
    if (recording.transcription) {
      showTranscriptionModal(recording.filename, recording);
    }
  });
  
  row.dataset.filename = recording.filename;
  row.dataset.status = recording.processing_status || '';
  return row;
}
```

**Add transcription modal function**:
```javascript
function showTranscriptionModal(filename, recording) {
  if (!recording.transcription) {
    alert('Transcription not available for this recording.');
    return;
  }
  
  // Create modal overlay
  const modal = document.createElement('div');
  modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
  modal.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Transcription</h2>
        <button class="close-modal text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
          <i class="fas fa-times text-2xl"></i>
        </button>
      </div>
      
      <div class="mb-4 space-y-2">
        <p class="text-sm text-gray-600 dark:text-gray-400">
          <strong>File:</strong> ${filename}
        </p>
        ${recording.speaker_names && recording.speaker_names.length > 0 ? `
          <p class="text-sm text-gray-600 dark:text-gray-400">
            <strong>Speakers:</strong> ${recording.speaker_names.join(', ')}
          </p>
        ` : ''}
        ${recording.category ? `
          <p class="text-sm text-gray-600 dark:text-gray-400">
            <strong>Category:</strong> ${recording.category}
          </p>
        ` : ''}
        ${recording.confidence ? `
          <p class="text-sm text-gray-600 dark:text-gray-400">
            <strong>Confidence:</strong> ${(recording.confidence * 100).toFixed(0)}%
          </p>
        ` : ''}
      </div>
      
      <div class="bg-gray-100 dark:bg-gray-700 rounded p-4">
        <p class="text-gray-900 dark:text-white whitespace-pre-wrap leading-relaxed">
          ${recording.transcription}
        </p>
      </div>
    </div>
  `;
  
  // Close on background click or X button
  modal.addEventListener('click', (e) => {
    if (e.target === modal || e.target.closest('.close-modal')) {
      document.body.removeChild(modal);
    }
  });
  
  document.body.appendChild(modal);
}
```

**Add auto-refresh for processing status**:
```javascript
// Poll for updates when recordings are processing
let refreshInterval = null;

function checkForProcessingRecordings() {
  const processingItems = document.querySelectorAll('[data-status="processing"],[data-status="pending"]');
  
  if (processingItems.length > 0 && !refreshInterval) {
    // Start polling every 10 seconds
    refreshInterval = setInterval(() => {
      console.log('Refreshing recordings (processing in progress)...');
      loadRecordings();
    }, 10000);
  } else if (processingItems.length === 0 && refreshInterval) {
    // Stop polling when nothing is processing
    clearInterval(refreshInterval);
    refreshInterval = null;
    console.log('All recordings processed, stopped polling');
  }
}

// Call after loading recordings
function loadRecordings() {
  // ... existing code ...
  
  // After creating all recording items
  checkForProcessingRecordings();
}
```

#### 3.3 Update config.html (Settings Page) with Tooltips

**Add OpenAI Configuration Section** (after existing configuration sections):
```html
<!-- OpenAI AI Processing Settings -->
<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 mb-6">
  <h2 class="text-2xl font-bold mb-4 text-gray-900 dark:text-white">
    <i class="fas fa-robot mr-2"></i>OpenAI AI Processing Settings
  </h2>
  
  <div class="space-y-4">
    <!-- Enable/Disable Toggle -->
    <div class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded">
      <div class="flex-1">
        <label class="font-semibold text-gray-900 dark:text-white flex items-center">
          Enable AI Processing
          <i class="fas fa-info-circle ml-2 text-blue-500 cursor-help" 
             title="Enable AI-powered transcription and metadata extraction for recordings"></i>
        </label>
        <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
          Automatically extract metadata from recordings using OpenAI
        </p>
      </div>
      <label class="relative inline-flex items-center cursor-pointer ml-4">
        <input type="checkbox" name="openai_enabled" 
               {{ 'checked' if config.get('openai_enabled') else '' }} 
               class="sr-only peer">
        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 
                    peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer 
                    dark:bg-gray-600 peer-checked:after:translate-x-full 
                    peer-checked:after:border-white after:content-[''] after:absolute 
                    after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 
                    after:border after:rounded-full after:h-5 after:w-5 after:transition-all 
                    dark:border-gray-600 peer-checked:bg-blue-600"></div>
      </label>
    </div>
    
    <!-- Auto-process Toggle -->
    <div class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded">
      <div class="flex-1">
        <label class="font-semibold text-gray-900 dark:text-white flex items-center">
          Auto-process New Recordings
          <i class="fas fa-info-circle ml-2 text-blue-500 cursor-help" 
             title="Automatically process new recordings when internet is available and phone is idle"></i>
        </label>
        <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
          Process recordings automatically (only when phone is idle)
        </p>
      </div>
      <label class="relative inline-flex items-center cursor-pointer ml-4">
        <input type="checkbox" name="openai_auto_process" 
               {{ 'checked' if config.get('openai_auto_process') else '' }} 
               class="sr-only peer">
        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 
                    peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer 
                    dark:bg-gray-600 peer-checked:after:translate-x-full 
                    peer-checked:after:border-white after:content-[''] after:absolute 
                    after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 
                    after:border after:rounded-full after:h-5 after:w-5 after:transition-all 
                    dark:border-gray-600 peer-checked:bg-blue-600"></div>
      </label>
    </div>
    
    <!-- OpenAI API Key -->
    <div>
      <label class="block font-semibold mb-2 text-gray-900 dark:text-white flex items-center">
        OpenAI API Key
        <i class="fas fa-info-circle ml-2 text-blue-500 cursor-help" 
           title="Your OpenAI API key (get one at platform.openai.com/api-keys). Starts with 'sk-'"></i>
      </label>
      <input type="password" name="openai_api_key" 
             value="{{ config.get('openai_api_key', '') }}" 
             placeholder="sk-proj-..."
             class="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600 font-mono text-sm">
      <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
        Get your API key at <a href="https://platform.openai.com/api-keys" target="_blank" class="text-blue-500 hover:underline">platform.openai.com/api-keys</a>
      </p>
    </div>
    
    <!-- GPT Model Selection -->
    <div>
      <label class="block font-semibold mb-2 text-gray-900 dark:text-white flex items-center">
        GPT Model
        <i class="fas fa-info-circle ml-2 text-blue-500 cursor-help" 
           title="AI model for metadata extraction. gpt-4o-mini is recommended for best cost/speed balance"></i>
      </label>
      <select name="openai_gpt_model" 
              class="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600">
        <option value="gpt-4o-mini" {{ 'selected' if config.get('openai_gpt_model') == 'gpt-4o-mini' else '' }}>
          GPT-4o Mini (Recommended - Fast & Cheap)
        </option>
        <option value="gpt-4o" {{ 'selected' if config.get('openai_gpt_model') == 'gpt-4o' else '' }}>
          GPT-4o (Higher Quality, More Expensive)
        </option>
      </select>
    </div>
    
    <!-- Language Selection -->
    <div>
      <label class="block font-semibold mb-2 text-gray-900 dark:text-white flex items-center">
        Language
        <i class="fas fa-info-circle ml-2 text-blue-500 cursor-help" 
           title="Primary language of recordings. Use 'en' for English, 'es' for Spanish, etc. or 'auto' for automatic detection"></i>
      </label>
      <input type="text" name="openai_language" 
             value="{{ config.get('openai_language', 'en') }}" 
             placeholder="en"
             class="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600">
      <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
        Examples: en (English), es (Spanish), fr (French), auto (detect)
      </p>
    </div>
    
    <!-- Minimum Duration -->
    <div>
      <label class="block font-semibold mb-2 text-gray-900 dark:text-white flex items-center">
        Minimum Duration (seconds)
        <i class="fas fa-info-circle ml-2 text-blue-500 cursor-help" 
           title="Skip processing recordings shorter than this (likely misdials or noise)"></i>
      </label>
      <input type="number" name="openai_min_duration" 
             value="{{ config.get('openai_min_duration', 5) }}" 
             min="0" max="60" step="1"
             class="w-full p-2 border rounded dark:bg-gray-700 dark:border-gray-600">
      <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
        Recordings shorter than this won't be processed (saves costs)
      </p>
    </div>
    
    <!-- Process Pending Button -->
    <div class="mt-6 p-4 bg-blue-50 dark:bg-blue-900 rounded">
      <div class="flex items-center justify-between">
        <div class="flex-1">
          <h3 class="font-semibold text-blue-900 dark:text-blue-100 flex items-center">
            Process Unprocessed Recordings
            <i class="fas fa-info-circle ml-2 text-blue-600 dark:text-blue-300 cursor-help" 
               title="Manually process recordings that were skipped (no internet, disabled, etc.)"></i>
          </h3>
          <p class="text-sm text-blue-700 dark:text-blue-300 mt-1">
            Manually process pending recordings (useful after regaining internet)
          </p>
        </div>
        <button id="process-pending-btn" 
                class="bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md px-4 py-2 
                       flex items-center shadow-sm transition-colors duration-200 ml-4">
          <i class="fas fa-sync-alt mr-2"></i>Process Now
        </button>
      </div>
      <div id="process-status" class="mt-2 text-sm"></div>
    </div>
  </div>
</div>
```

**Add JavaScript for Process Button**:
```javascript
// Process pending recordings button handler
document.getElementById('process-pending-btn')?.addEventListener('click', async () => {
  const btn = document.getElementById('process-pending-btn');
  const status = document.getElementById('process-status');
  
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processing...';
  status.textContent = 'Queueing recordings for processing...';
  status.className = 'mt-2 text-sm text-blue-600 dark:text-blue-300';
  
  try {
    const response = await fetch('/api/process-pending', {
      method: 'POST'
    });
    const data = await response.json();
    
    if (data.success) {
      status.textContent = data.message;
      status.className = 'mt-2 text-sm text-green-600 dark:text-green-300';
    } else {
      throw new Error(data.message || 'Failed to process recordings');
    }
  } catch (error) {
    status.textContent = `Error: ${error.message}`;
    status.className = 'mt-2 text-sm text-red-600 dark:text-red-300';
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-sync-alt mr-2"></i>Process Now';
  }
});
```

### Phase 4: Testing & Deployment

#### 4.1 Local Testing (Development Machine)

1. **Install dependencies**:
   ```bash
   pip install openai requests
   ```

2. **Create test environment**:
   - Add OpenAI API key to `config.yaml`
   - Enable OpenAI processing
   - Create test audio files in recordings directory

3. **Test components individually**:
   - Metadata manager: read/write operations
   - Connectivity checker: internet detection
   - OpenAI processor: transcription + metadata extraction
   - Job queue: queuing and processing

4. **Test API endpoints**:
   - `/api/recordings` - returns metadata
   - `/api/process-pending` - manual processing
   - `/api/transcription/<filename>` - get transcription

5. **Test UI**:
   - Verify message titles display
   - Check speaker names column
   - Verify category badges with colors
   - Test transcription modal
   - Check processing status indicators

#### 4.2 Integration Testing

1. **Full recording flow**:
   - Make a test recording via phone
   - Verify file created
   - Check metadata JSON initialized
   - Confirm queuing happens
   - Wait for idle state
   - Verify processing completes
   - Check UI updates with AI data

2. **Offline scenarios**:
   - Disable internet
   - Make recording
   - Verify marked as "pending"
   - Re-enable internet
   - Use "Process Now" button
   - Confirm processing succeeds

3. **Idle-time processing**:
   - Queue multiple recordings
   - Make a new call (phone active)
   - Verify processing pauses
   - Hang up (phone idle)
   - Verify processing resumes

4. **Error handling**:
   - Invalid API key
   - Short/empty audio files
   - Network timeouts
   - Malformed responses

#### 4.3 Raspberry Pi Deployment

1. **SSH into Raspberry Pi**:
   ```bash
   ssh admin@<raspberry-pi-ip>
   ```

2. **Update code**:
   ```bash
   cd ~/rotary-phone-audio-guestbook
   git pull
   ```

3. **Install dependencies**:
   ```bash
   pip install openai
   ```

4. **Update config.yaml**:
   - Add OpenAI API key via web interface or manually
   - Enable OpenAI processing
   - Set language preferences

5. **Restart services**:
   ```bash
   sudo systemctl restart audioGuestBook.service
   sudo systemctl restart gunicorn
   ```

6. **Monitor logs**:
   ```bash
   # AudioGuestBook logs
   journalctl -u audioGuestBook.service -f
   
   # Gunicorn/Flask logs
   journalctl -u gunicorn -f
   ```

7. **Test with real recording**:
   - Make a test call
   - Check logs for AI processing
   - Verify web UI shows metadata

#### 4.4 Production Validation

1. **Verify metadata file**: Check `recordings_metadata.json` exists and has valid structure
2. **Check AI data quality**: Review transcriptions and extracted metadata
3. **Monitor costs**: Check OpenAI usage dashboard
4. **Test manual processing**: Use "Process Now" button for any pending recordings
5. **Verify idle-time processing**: Ensure processing doesn't interrupt calls

## File Structure

```
rotary-phone-audio-guestbook/
├── config.yaml (updated with OpenAI config)
├── recordings/
│   ├── recordings_metadata.json (new)
│   ├── 2024-12-01T15:30:45.wav
│   └── ...
├── webserver/
│   ├── server.py (updated)
│   ├── metadata_manager.py (new)
│   ├── connectivity_checker.py (new)
│   ├── openai_processor.py (new)
│   ├── job_queue.py (new)
│   ├── static/
│   │   └── js/
│   │       └── recordings.js (updated)
│   └── templates/
│       ├── index.html (updated)
│       └── config.html (updated)
└── src/
    └── audioGuestBook.py (updated)
```

## Monitoring & Maintenance

### Cost Monitoring
1. Check OpenAI usage at [platform.openai.com/usage](https://platform.openai.com/usage)
2. Set usage limits in OpenAI dashboard to prevent overcharges
3. Monitor costs per event to track spending

### Logs to Monitor
1. **Processing Queue**: Check for backlog or stuck items
2. **OpenAI API Errors**: Monitor for rate limits, auth failures
3. **Metadata File**: Verify JSON integrity (no corruption)
4. **Internet Connectivity**: Track when processing is skipped due to offline status

### Maintenance Tasks
1. **After Events**: Backup `recordings_metadata.json`
2. **Monthly**: Review failed recordings and retry if needed
3. **As Needed**: Update OpenAI API key if rotated
4. **Quarterly**: Review prompt effectiveness and adjust if needed

## Rollback Plan

If issues occur:
1. Set `openai_enabled: false` in config or via web UI
2. Restart services: `sudo systemctl restart audioGuestBook.service gunicorn`
3. System continues to work with filenames only (no AI metadata)
4. Metadata JSON preserved - can reprocess later

## Future Enhancements

1. **Multi-language Support**: Automatic language detection
2. **Batch Export**: Export all transcriptions to PDF/Word
3. **Search**: Full-text search across all transcriptions
4. **Statistics**: Dashboard showing category distributions, popular names, etc.
5. **Sentiment Analysis**: Add emotional sentiment scores
6. **Highlights**: Automatically extract best quotes
7. **Voice Analysis**: Identify unique speakers across recordings

## Questions & Next Steps

**Outstanding Questions**:
1. Confirm preferred language setting (English only or multi-language?)
2. Should we add processing delay to allow deleting bad recordings first?
3. Preferred minimum duration threshold (5 seconds recommended)

**Ready to Implement**:
All features documented and ready for implementation. Start with Phase 1 (Dependencies) and proceed through phases sequentially.

