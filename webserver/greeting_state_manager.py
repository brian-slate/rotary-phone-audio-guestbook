import json
import logging
import threading
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class GreetingStateManager:
    """Thread-safe manager for greeting rotation state stored in JSON."""
    
    def __init__(self, recordings_path: str):
        self.recordings_path = Path(recordings_path)
        self.state_file = self.recordings_path / "greeting_state.json"
        self.lock = threading.Lock()
        self._ensure_state_file()
    
    def _ensure_state_file(self):
        """Create state file if it doesn't exist."""
        if not self.state_file.exists():
            self._write_state({"current_index": 0, "last_updated": ""})
            logger.info(f"Created greeting state file: {self.state_file}")
    
    def _read_state(self) -> dict:
        """Read state from JSON file."""
        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error reading greeting state: {e}")
            return {"current_index": 0, "last_updated": ""}
    
    def _write_state(self, data: dict):
        """Write state to JSON file."""
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_next_greeting(self, greeting_files: List[str]) -> str:
        """Get the next greeting file in sequence and increment index.
        
        Args:
            greeting_files: List of greeting file paths to cycle through
            
        Returns:
            Path to the next greeting file
        """
        if not greeting_files:
            logger.warning("No greeting files provided, cannot get next greeting")
            return ""
        
        with self.lock:
            state = self._read_state()
            current_index = state.get("current_index", 0)
            
            # Ensure index is within bounds
            if current_index >= len(greeting_files):
                current_index = 0
            
            # Get current greeting
            greeting = greeting_files[current_index]
            
            # Increment for next time (wrap around)
            next_index = (current_index + 1) % len(greeting_files)
            
            # Update state
            import time
            state["current_index"] = next_index
            state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._write_state(state)
            
            logger.info(f"Selected greeting {current_index + 1}/{len(greeting_files)}: {Path(greeting).name}")
            
            return greeting
    
    def reset_index(self):
        """Reset the greeting index to 0."""
        with self.lock:
            state = self._read_state()
            state["current_index"] = 0
            import time
            state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._write_state(state)
            logger.info("Reset greeting index to 0")
    
    def get_current_index(self) -> int:
        """Get the current greeting index."""
        with self.lock:
            state = self._read_state()
            return state.get("current_index", 0)
