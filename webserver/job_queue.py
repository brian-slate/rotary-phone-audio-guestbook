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
    
    def _worker(self):
        """Background worker - processes queue only when phone is idle."""
        while self.running:
            task_retrieved = False
            try:
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
                # Only call task_done if we actually got a task from the queue
                if task_retrieved:
                    self.queue.task_done()
