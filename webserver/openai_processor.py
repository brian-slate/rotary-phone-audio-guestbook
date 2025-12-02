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
        self.compress_audio = config.get('openai_compress_audio', True)
        self.convert_to_mono = config.get('openai_convert_to_mono', True)
        self.target_sample_rate = config.get('openai_target_sample_rate', 16000)
        self.max_retries = config.get('openai_max_retries', 3)
        self.retry_delay = config.get('openai_retry_delay', 30)
        self.ignored_names = config.get('openai_ignored_names', [])
        self.categories = config.get('openai_categories', [
            "joyful", "heartfelt", "humorous", "nostalgic", "advice", 
            "blessing", "toast", "gratitude", "apology", "other"
        ])
        
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
        ignored_names_note = ""
        examples_note = ""
        if self.ignored_names:
            ignored_names_list = ', '.join(self.ignored_names)
            ignored_names_note = f"\n\n   ⚠️  CRITICAL: NEVER include these names in the 'names' array: {ignored_names_list}"
            ignored_names_note += f"\n   These are the wedding couple/event hosts, NOT the guests leaving messages."
            ignored_names_note += f"\n   Example: If message says 'Hi Cam and Lara, this is Mike', only extract 'Mike'"
            ignored_names_note += f"\n   Example: If message says 'Cam, wishing you happiness', extract NO names (empty array)"
        
        categories_str = ", ".join(self.categories)
        prompt = f"""Analyze this wedding/event guestbook message and extract:

1. Speaker names mentioned (full first and last names if available, otherwise just first names)
   - ONLY include people who are SPEAKING, CALLING, or introducing themselves as guests
   - Do NOT include recipients, hosts, or people being addressed{ignored_names_note}
2. Emotional category (choose one: {categories_str})
3. A brief 4-7 word title summarizing the message
4. Confidence score (0.0-1.0) based on clarity

Transcription:
{transcription}

Respond ONLY with valid JSON in this exact format:
{{
  "names": ["John Smith", "Jane Doe"],
  "category": "joyful",
  "summary": "Brief message title here",
  "confidence": 0.95
}}"""
        
        # GPT-5 models use a different API (responses endpoint with reasoning control)
        if "gpt-5" in self.gpt_model.lower():
            logger.info(f"Using {self.gpt_model} with reasoning.effort=none (no reasoning)")
            response = self.client.responses.create(
                model=self.gpt_model,
                input=prompt,
                reasoning={"effort": "none"},  # Disable reasoning completely
                text={"format": "json"},
                max_output_tokens=800
            )
            # Extract content from responses API format
            content = response.output[0].content if response.output else None
        else:
            # GPT-4 and older models use chat completions API
            response = self.client.chat.completions.create(
                model=self.gpt_model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=800,
                response_format={"type": "json_object"}
            )
            # Extract content from chat completions API format
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "length":
                logger.error(f"GPT response hit token limit (max_completion_tokens=800)")
                logger.error(f"Model: {self.gpt_model}, Tokens used: {response.usage}")
                raise ValueError("GPT response exceeded token limit - message may be too long")
            content = response.choices[0].message.content
        
        # Content already extracted above based on API type
        if not content or content.strip() == "":
            logger.error(f"Empty response from GPT model {self.gpt_model}")
            logger.error(f"Finish reason: {finish_reason}, Full response: {response}")
            raise ValueError("GPT returned empty content")
        
        try:
            metadata = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response as JSON: {content[:500]}")
            raise
        
        # Post-process: Filter out ignored names (case-insensitive)
        if self.ignored_names and 'names' in metadata:
            ignored_lower = [name.lower() for name in self.ignored_names]
            original_names = metadata['names']
            
            # Filter out any name that matches ignored names (case-insensitive, partial match)
            filtered_names = []
            for name in original_names:
                name_lower = name.lower()
                # Check if any ignored name appears in this name
                if not any(ignored in name_lower for ignored in ignored_lower):
                    filtered_names.append(name)
            
            if len(filtered_names) != len(original_names):
                logger.info(f"Filtered names: {original_names} → {filtered_names} (removed ignored names)")
            
            metadata['names'] = filtered_names
        
        return metadata
