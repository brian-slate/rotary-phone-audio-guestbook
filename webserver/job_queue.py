import logging
import queue
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessingQueue:
    """Background queue for processing recordings only when phone is idle."""
    
    def __init__(self, processor, metadata_manager, connectivity_checker,
                 phone_state_checker, config):
        self.queue = queue.Queue()
        self.processor = processor
        self.metadata_manager = metadata_manager
        self.connectivity_checker = connectivity_checker
        self.phone_state_checker = phone_state_checker
        self.config = config
        self.running = False
        self.worker_thread = None
        self.last_recording_time = 0  # Track when last recording was made
        self.cooldown_seconds = config.get('openai_processing_cooldown', 120)
        self.allow_processing_during_call = config.get('openai_allow_processing_during_call', False)
        self.last_error = None  # Track last processing error
        self.last_error_time = None  # When the error occurred
        self.is_processing = False  # Track if actively processing (for LED indicator)
        self.processing_callback = None  # Callback to notify when processing state changes
    
    def start(self):
        """Start background worker thread."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name="AI-ProcessingQueue"
            )
            self.worker_thread.start()
            logger.info("AI processing queue started")
            # Clear any stale error on startup
            self.clear_last_error()
            # Scan for any pending recordings and enqueue them
            self._scan_and_enqueue_pending()
    
    def stop(self):
        """Stop background worker."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        logger.info("AI processing queue stopped")
    
    def enqueue(self, audio_file_path: str, filename: str):
        """Add recording to processing queue."""
        # Update last recording time
        self.last_recording_time = time.time()
        
        if self.config.get('openai_auto_process', True):
            self.queue.put((audio_file_path, filename))
            logger.info(f"Queued {filename} for AI processing")
        else:
            logger.info(f"Auto-process disabled, skipping {filename}")
            self.metadata_manager.update_metadata(filename, {
                'ai_metadata': {'processing_status': 'skipped'}
            })
    
    def _scan_and_enqueue_pending(self):
        """Scan metadata for pending recordings and enqueue them."""
        try:
            unprocessed = self.metadata_manager.get_unprocessed_recordings()
            if unprocessed:
                logger.info(f"Found {len(unprocessed)} pending recording(s) to process")
                for rec in unprocessed:
                    filename = rec['filename']
                    recordings_path = Path(self.config['recordings_path'])
                    file_path = recordings_path / filename
                    if file_path.exists():
                        self.queue.put((str(file_path), filename))
                        logger.info(f"Enqueued pending recording: {filename}")
                    else:
                        logger.warning(f"Pending recording not found: {filename}")
            else:
                logger.info("No pending recordings found")
        except Exception as e:
            logger.error(f"Error scanning for pending recordings: {e}")
        
    # -------- Error tracking helpers --------
    def _error_file_path(self) -> Path:
        base_dir = Path(__file__).parent.parent  # project root
        return base_dir / 'webserver' / 'last_openai_error.json'

    def set_last_error(self, message: str):
        """Persist last API/processing error to a small JSON file."""
        import json
        from datetime import datetime
        self.last_error = message
        self.last_error_time = time.time()
        payload = {
            'message': message,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        try:
            path = self._error_file_path()
            path.write_text(json.dumps(payload))
            logger.debug(f"Wrote last error to {path}")
        except Exception as e:
            logger.warning(f"Failed to persist last error: {e}")

    def get_last_error(self):
        """Return the last error dict if available, else None."""
        import json
        path = self._error_file_path()
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return {'message': self.last_error, 'timestamp': self.last_error_time}
        return None

    def clear_last_error(self):
        """Clear persisted error and in-memory error state."""
        self.last_error = None
        self.last_error_time = None
        path = self._error_file_path()
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logger.warning(f"Failed to clear last error file: {e}")
    
    def _worker(self):
        """Background worker - processes queue only when phone is idle."""
        last_scan_time = 0
        has_pending = False  # Track if we found pending recordings last scan
        
        while self.running:
            task_retrieved = False
            try:
                # Dynamically adjust scan interval based on whether we have pending work
                # Scan every 3s when pending, every 30s when idle
                scan_interval = 3 if has_pending else 30
                
                # Periodically scan for pending recordings that aren't in queue
                current_time = time.time()
                if current_time - last_scan_time > scan_interval:
                    unprocessed = self.metadata_manager.get_unprocessed_recordings()
                    has_pending = len(unprocessed) > 0
                    if has_pending:
                        self._scan_and_enqueue_pending()
                    last_scan_time = current_time
                
                # Non-blocking get with timeout
                try:
                    audio_file_path, filename = self.queue.get(timeout=1.0)
                    task_retrieved = True
                except queue.Empty:
                    continue
                
                # CRITICAL: Wait for appropriate conditions before processing
                # 1. Check if we should wait for phone to be idle
                if not self.allow_processing_during_call:
                    while self.phone_state_checker() and self.running:
                        logger.debug("Phone active, waiting to process...")
                        time.sleep(5)  # Check every 5 seconds
                    
                    if not self.running:
                        break
                
                # 2. Check cooldown period - wait after last recording
                time_since_last_recording = time.time() - self.last_recording_time
                if time_since_last_recording < self.cooldown_seconds:
                    wait_time = self.cooldown_seconds - time_since_last_recording
                    logger.info(f"Cooldown period: waiting {wait_time:.0f}s before processing...")
                    time.sleep(wait_time)
                
                # 3. Double-check phone is still idle after cooldown
                if not self.allow_processing_during_call and self.phone_state_checker():
                    logger.info("Phone became active during cooldown, re-queuing")
                    self.queue.put((audio_file_path, filename))
                    continue
                
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
                self.is_processing = True
                if self.processing_callback:
                    self.processing_callback(True)  # Notify: AI started
                
                result = self.processor.process_recording(audio_file_path, filename)
                
                self.is_processing = False
                if self.processing_callback:
                    self.processing_callback(False)  # Notify: AI finished
                
                if result:
                    # Update metadata with results
                    self.metadata_manager.mark_as_completed(filename, result)
                    logger.info(f"Successfully processed {filename}")
                    # Clear any prior error on successful processing
                    self.clear_last_error()
                else:
                    self.metadata_manager.mark_as_failed(
                        filename,
                        "Transcription empty or too short"
                    )
            
            except Exception as e:
                logger.error(f"Processing error for {filename}: {e}")
                self.is_processing = False
                if self.processing_callback:
                    self.processing_callback(False)  # Notify: AI finished (with error)
                self.metadata_manager.mark_as_failed(filename, str(e))
                # Persist last error for display in UI without disabling processing
                self.set_last_error(str(e))
            
            finally:
                # Only call task_done if we actually got a task from the queue
                if task_retrieved:
                    self.queue.task_done()
