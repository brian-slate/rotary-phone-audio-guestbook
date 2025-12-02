import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MetadataManager:
    """Thread-safe manager for recordings metadata stored in JSON."""
    
    def __init__(self, recordings_path: str):
        self.recordings_path = Path(recordings_path)
        self.metadata_file = self.recordings_path / "recordings_metadata.json"
        self.lock = threading.Lock()
        self._ensure_metadata_file()
    
    def _ensure_metadata_file(self):
        """Create metadata file if it doesn't exist."""
        if not self.metadata_file.exists():
            self._write_metadata({"version": "1.0", "recordings": {}})
            logger.info(f"Created metadata file: {self.metadata_file}")
    
    def _read_metadata(self) -> Dict:
        """Read metadata from JSON file."""
        try:
            with open(self.metadata_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error reading metadata: {e}")
            return {"version": "1.0", "recordings": {}}
    
    def _write_metadata(self, data: Dict):
        """Write metadata to JSON file."""
        with open(self.metadata_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def initialize_recording(self, filename: str, file_size: int):
        """Create initial metadata entry for a new recording."""
        with self.lock:
            data = self._read_metadata()
            
            # Get file creation time from filesystem
            file_path = self.recordings_path / filename
            created_at = None
            duration_seconds = None
            
            if file_path.exists():
                import datetime
                created_at = datetime.datetime.fromtimestamp(
                    file_path.stat().st_ctime
                ).isoformat()
            
            data["recordings"][filename] = {
                "filename": filename,
                "created_at": created_at,
                "duration_seconds": duration_seconds,
                "file_size_bytes": file_size,
                "ai_metadata": {
                    "processing_status": "pending"
                }
            }
            
            self._write_metadata(data)
            logger.info(f"Initialized metadata for {filename}")
    
    def mark_as_processing(self, filename: str):
        """Mark recording as currently being processed."""
        with self.lock:
            data = self._read_metadata()
            if filename in data["recordings"]:
                data["recordings"][filename]["ai_metadata"]["processing_status"] = "processing"
                self._write_metadata(data)
                logger.info(f"Marked {filename} as processing")
    
    def mark_as_completed(self, filename: str, ai_data: Dict):
        """Mark recording as completed with AI metadata."""
        with self.lock:
            data = self._read_metadata()
            if filename in data["recordings"]:
                data["recordings"][filename]["ai_metadata"] = {
                    **ai_data,
                    "processing_status": "completed",
                    "processed_at": time.strftime("%Y-%m-%dT%H:%M:%S")
                }
                self._write_metadata(data)
                logger.info(f"Marked {filename} as completed")
    
    def mark_as_failed(self, filename: str, error: str):
        """Mark recording as failed with error message."""
        with self.lock:
            data = self._read_metadata()
            if filename in data["recordings"]:
                data["recordings"][filename]["ai_metadata"] = {
                    "processing_status": "failed",
                    "error": error,
                    "processed_at": time.strftime("%Y-%m-%dT%H:%M:%S")
                }
                self._write_metadata(data)
                logger.warning(f"Marked {filename} as failed: {error}")
    
    def update_metadata(self, filename: str, metadata: Dict):
        """Update metadata for a recording."""
        with self.lock:
            data = self._read_metadata()
            if filename not in data["recordings"]:
                data["recordings"][filename] = {"filename": filename}
            
            # Merge metadata
            for key, value in metadata.items():
                if key == "ai_metadata" and isinstance(value, dict):
                    if "ai_metadata" not in data["recordings"][filename]:
                        data["recordings"][filename]["ai_metadata"] = {}
                    data["recordings"][filename]["ai_metadata"].update(value)
                else:
                    data["recordings"][filename][key] = value
            
            self._write_metadata(data)
    
    def get_metadata(self, filename: str) -> Optional[Dict]:
        """Get metadata for a single recording."""
        with self.lock:
            data = self._read_metadata()
            return data["recordings"].get(filename)
    
    def get_all_recordings(self) -> List[Dict]:
        """Get all recordings with metadata, including files not yet in JSON."""
        with self.lock:
            data = self._read_metadata()
            recordings = []
            
            # Get all WAV files from filesystem
            if self.recordings_path.exists():
                for file_path in self.recordings_path.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() == ".wav":
                        filename = file_path.name
                        
                        # Get metadata if it exists, otherwise create basic info
                        if filename in data["recordings"]:
                            recordings.append(data["recordings"][filename])
                        else:
                            # File exists but not in metadata
                            recordings.append({
                                "filename": filename,
                                "created_at": None,
                                "file_size_bytes": file_path.stat().st_size,
                                "ai_metadata": None
                            })
            
            # Sort by creation time (newest first)
            recordings.sort(
                key=lambda x: x.get("created_at") or x.get("filename"),
                reverse=True
            )
            
            return recordings
    
    def get_unprocessed_recordings(self) -> List[Dict]:
        """Get recordings that need AI processing."""
        with self.lock:
            data = self._read_metadata()
            unprocessed = []
            
            for filename, rec in data["recordings"].items():
                ai_meta = rec.get("ai_metadata", {})
                status = ai_meta.get("processing_status")
                
                if status in ["pending", "failed", None]:
                    # Check file still exists
                    if (self.recordings_path / filename).exists():
                        unprocessed.append(rec)
            
            return unprocessed
    
    def remove_recording(self, filename: str):
        """Remove metadata entry for a deleted recording."""
        with self.lock:
            data = self._read_metadata()
            if filename in data["recordings"]:
                del data["recordings"][filename]
                self._write_metadata(data)
                logger.info(f"Removed metadata for deleted recording: {filename}")
            else:
                logger.warning(f"Attempted to remove metadata for non-existent entry: {filename}")
