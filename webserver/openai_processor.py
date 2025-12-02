import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Process audio recordings with OpenAI Whisper and GPT-4o Mini."""
    
    def __init__(self, config: dict):
        self.enabled = config.get('openai_enabled', False)
        self.gpt_model = config.get('openai_gpt_model', 'gpt-4o-mini')
        self.language = config.get('openai_language', 'en')
        self.min_duration = config.get('openai_min_duration', 5)
        self.compress_audio = config.get('openai_compress_audio', True)
        self.convert_to_mono = config.get('openai_convert_to_mono', True)
        self.target_sample_rate = config.get('openai_target_sample_rate', 16000)
        self.max_retries = config.get('openai_max_retries', 3)
        self.retry_delay = config.get('openai_retry_delay', 30)
        
        if self.enabled:
            try:
                from openai import OpenAI
                api_key = config.get('openai_api_key', '')
                if not api_key:
                    logger.warning("OpenAI API key not configured")
                    self.enabled = False
                else:
                    self.client = OpenAI(api_key=api_key)
                    logger.info("OpenAI client initialized successfully")
            except ImportError:
                logger.error("OpenAI library not installed. Run: pip install openai")
                self.enabled = False
    
    def process_recording(self, audio_file_path: str, filename: str) -> dict:
        """Process a recording through Whisper + GPT pipeline."""
        if not self.enabled:
            raise ValueError("OpenAI processing not enabled")
        
        compressed_file = None
        try:
            # 1. Compress audio if enabled
            file_to_upload = audio_file_path
            if self.compress_audio:
                logger.info(f"Compressing {filename} for upload...")
                compressed_file = self._compress_audio(audio_file_path)
                if compressed_file:
                    original_size = Path(audio_file_path).stat().st_size
                    compressed_size = Path(compressed_file).stat().st_size
                    reduction = (1 - compressed_size / original_size) * 100
                    logger.info(f"Compressed {filename}: {original_size/1024:.1f}KB → {compressed_size/1024:.1f}KB ({reduction:.1f}% reduction)")
                    file_to_upload = compressed_file
            
            # 2. Transcribe with Whisper API (with retries)
            logger.info(f"Transcribing {filename} with Whisper...")
            transcription = self._transcribe_with_whisper_retry(file_to_upload)
            
            if not transcription or len(transcription.strip()) < 10:
                logger.warning(f"Transcription too short or empty for {filename}")
                return None
            
            # 3. Extract metadata with GPT (with retries)
            logger.info(f"Extracting metadata for {filename} with GPT...")
            metadata = self._extract_metadata_with_gpt_retry(transcription)
            
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
        finally:
            # Clean up temporary compressed file
            if compressed_file and Path(compressed_file).exists():
                try:
                    Path(compressed_file).unlink()
                    logger.debug(f"Cleaned up temporary file: {compressed_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file: {e}")
    
    def _compress_audio(self, audio_file_path: str) -> str:
        """Compress WAV to MP3 with optional mono conversion and sample rate adjustment."""
        try:
            # Create temp file for compressed audio
            temp_fd, temp_path = tempfile.mkstemp(suffix='.mp3')
            
            # Build ffmpeg command
            cmd = ['ffmpeg', '-i', audio_file_path]
            
            # Convert to mono if enabled
            if self.convert_to_mono:
                cmd.extend(['-ac', '1'])
            
            # Set target sample rate
            cmd.extend(['-ar', str(self.target_sample_rate)])
            
            # MP3 encoding settings (128kbps is good for speech)
            cmd.extend(['-codec:a', 'libmp3lame', '-b:a', '128k'])
            
            # Overwrite output and suppress output
            cmd.extend(['-y', temp_path])
            
            # Run ffmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            return temp_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg compression failed: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("FFmpeg not found. Install with: sudo apt-get install ffmpeg")
            return None
        except Exception as e:
            logger.error(f"Audio compression error: {e}")
            return None
    
    def _transcribe_with_whisper_retry(self, audio_file_path: str) -> str:
        """Transcribe audio with Whisper API with retry logic."""
        for attempt in range(self.max_retries):
            try:
                return self._transcribe_with_whisper(audio_file_path)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Whisper API attempt {attempt + 1} failed: {e}. Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Whisper API failed after {self.max_retries} attempts")
                    raise
    
    def _transcribe_with_whisper(self, audio_file_path: str) -> str:
        """Transcribe audio with OpenAI Whisper API."""
        with open(audio_file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=self.language if self.language != 'auto' else None,
                response_format="text"
            )
        return transcript
    
    def _extract_metadata_with_gpt_retry(self, transcription: str) -> dict:
        """Extract metadata with GPT with retry logic."""
        for attempt in range(self.max_retries):
            try:
                return self._extract_metadata_with_gpt(transcription)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"GPT API attempt {attempt + 1} failed: {e}. Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"GPT API failed after {self.max_retries} attempts")
                    raise
    
    def _extract_metadata_with_gpt(self, transcription: str) -> dict:
        """Use GPT-4o Mini to extract metadata from transcription."""
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
        
        response = self.client.chat.completions.create(
            model=self.gpt_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        metadata = json.loads(content)
        return metadata
