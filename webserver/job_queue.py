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
        self.auto_process_enabled = config.get('openai_auto_process', False)
    
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
            # Reset stale 'processing' entries to 'pending'
            self._reset_stale_processing()
            # Clean up orphaned recordings (files never queued for AI)
            self._cleanup_orphaned_recordings()
            # Scan for any pending recordings and enqueue them
            # Only auto-scan on startup if auto-process is enabled
            if self.auto_process_enabled:
                self._scan_and_enqueue_pending(force=False)
    
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
        
        # Check if automatic AI processing is enabled
        if self.auto_process_enabled and self.config.get('openai_api_key'):
            self.queue.put((audio_file_path, filename))
            logger.info(f"Queued {filename} for automatic AI processing")
        else:
            # Auto-process disabled: do NOT set 'pending' to avoid confusing UI.
            # Force-process endpoint will discover recordings without ai_metadata.
            logger.info(f"Auto-process disabled; leaving {filename} unqueued (visible for manual processing)")
    
    def _reset_stale_processing(self):
        """Reset recordings stuck in 'processing' for too long back to 'pending'."""
        try:
            import datetime as _dt
            data = self.metadata_manager._read_metadata()
            if not data:
                return
            threshold = self.config.get('openai_processing_stale_seconds', 300)
            reset = 0
            for filename, rec in data.get('recordings', {}).items():
                ai = rec.get('ai_metadata', {})
                if ai.get('processing_status') == 'processing':
                    started = ai.get('processing_started_at')
                    if started:
                        try:
                            started_dt = _dt.datetime.strptime(started, "%Y-%m-%dT%H:%M:%S")
                            age = (_dt.datetime.utcnow() - started_dt).total_seconds()
                        except Exception:
                            age = threshold + 1
                    else:
                        age = threshold + 1
                    if age > threshold:
                        ai.clear()
                        ai['processing_status'] = 'pending'
                        reset += 1
                        logger.warning(f"Reset stale processing for {filename} (age {age:.0f}s > {threshold}s)")
            if reset:
                self.metadata_manager._write_metadata(data)
                logger.info(f"Reset {reset} stale recording(s) to pending on startup")
        except Exception as e:
            logger.error(f"Error resetting stale processing: {e}")
    
    def _cleanup_orphaned_recordings(self):
        """Queue orphaned WAV files and delete metadata entries for missing files."""
        try:
            import wave
            recordings_path = Path(self.config['recordings_path'])
            if not recordings_path.exists():
                return
            
            min_duration = self.config.get('minimum_message_duration', 2.0)
            orphaned_wavs_queued = 0
            junk_deleted = 0
            orphaned_metadata_cleaned = 0
            
            # Step 1: Find WAV files without metadata and queue them (or delete if too short)
            for file_path in recordings_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == ".wav":
                    filename = file_path.name
                    metadata = self.metadata_manager.get_metadata(filename)
                    
                    # No metadata? Check duration then either delete (junk) or queue (orphan)
                    if not metadata or not metadata.get('ai_metadata'):
                        try:
                            with wave.open(str(file_path), 'rb') as wav:
                                frames = wav.getnframes()
                                rate = wav.getframerate()
                                duration = frames / float(rate)
                                
                                if duration < min_duration:
                                    # Too short - delete as junk
                                    file_path.unlink()
                                    if metadata:
                                        self.metadata_manager.remove_recording(filename)
                                    logger.info(f"Deleted junk recording (too short {duration:.1f}s < {min_duration}s): {filename}")
                                    junk_deleted += 1
                                else:
                                    # Valid duration but no metadata - initialize and queue
                                    file_size = file_path.stat().st_size
                                    self.metadata_manager.initialize_recording(filename, file_size)
                                    logger.info(f"Initialized orphaned WAV file: {filename} ({duration:.1f}s)")
                                    orphaned_wavs_queued += 1
                        except Exception as e:
                            logger.warning(f"Could not read duration for {filename}: {e}")
            
            # Step 2: Clean up metadata entries for files that no longer exist
            data = self.metadata_manager._read_metadata()
            files_to_remove = []
            for filename in data.get('recordings', {}).keys():
                file_path = recordings_path / filename
                if not file_path.exists():
                    files_to_remove.append(filename)
            
            if files_to_remove:
                for filename in files_to_remove:
                    self.metadata_manager.remove_recording(filename)
                    logger.info(f"Removed orphaned metadata entry (no WAV file): {filename}")
                    orphaned_metadata_cleaned += 1
            
            if orphaned_wavs_queued > 0 or junk_deleted > 0 or orphaned_metadata_cleaned > 0:
                logger.info(f"Cleanup: queued {orphaned_wavs_queued} orphaned WAVs, deleted {junk_deleted} junk recordings, cleaned {orphaned_metadata_cleaned} orphaned metadata entries")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def _scan_and_enqueue_pending(self, force: bool):
        """Scan metadata for unprocessed recordings and enqueue them.
        
        If force is False, only enqueue when auto-process is enabled.
        If force is True (triggered by user), always enqueue.
        """
        try:
            if not force and not self.auto_process_enabled:
                logger.debug("Auto-process disabled; skipping background scan.")
                return
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
        signal_file = Path(self.config['recordings_path']) / '.force_process_trigger'
        last_signal_check = 0
        
        while self.running:
            task_retrieved = False
            try:
                # Check for force process trigger file (immediate response)
                current_time = time.time()
                if signal_file.exists():
                    try:
                        signal_file.unlink()  # Remove trigger immediately
                        logger.info("Force process trigger detected, scanning for pending recordings")
                        self._scan_and_enqueue_pending(force=True)
                        last_scan_time = current_time
                        has_pending = True
                    except Exception as e:
                        logger.error(f"Error processing trigger file: {e}")
                
                # Dynamically adjust scan interval based on whether we have pending work
                # Scan every 10s when pending, every 60s when idle (reduced overhead since we have trigger)
                scan_interval = 10 if has_pending else 60
                
                # Periodically scan only if auto-process is enabled
                if self.auto_process_enabled and current_time - last_scan_time > scan_interval:
                    unprocessed = self.metadata_manager.get_unprocessed_recordings()
                    has_pending = len(unprocessed) > 0
                    if has_pending:
                        self._scan_and_enqueue_pending(force=False)
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
                
                # Check current status - skip if already completed
                current_meta = self.metadata_manager.get_metadata(filename)
                if current_meta:
                    status = current_meta.get('ai_metadata', {}).get('processing_status')
                    if status == 'completed':
                        logger.info(f"Skipping {filename} - already completed")
                        continue
                
                # Check if we have an API key (required for processing)
                if not self.config.get('openai_api_key'):
                    logger.warning(f"No API key configured, cannot process {filename}")
                    self.metadata_manager.update_metadata(filename, {
                        'ai_metadata': {'processing_status': 'failed', 'error': 'No API key configured'}
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
                    # Transcription empty/too short - delete the recording
                    logger.info(f"Transcription empty for {filename}, deleting recording...")
                    try:
                        if file_path.exists():
                            file_path.unlink()
                            logger.info(f"Deleted silent/empty recording: {filename}")
                        # Remove metadata entry
                        self.metadata_manager.remove_recording(filename)
                    except Exception as del_err:
                        logger.error(f"Failed to delete {filename}: {del_err}")
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
