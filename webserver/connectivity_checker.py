import logging
import time

logger = logging.getLogger(__name__)


class ConnectivityChecker:
    """Check internet connectivity with result caching."""
    
    def __init__(self, cache_duration=60):
        self.cache_duration = cache_duration
        self.last_check_time = 0
        self.last_result = False
    
    def check_internet_available(self) -> bool:
        """Check if internet is available (cached for 60 seconds)."""
        current_time = time.time()
        
        # Return cached result if recent
        if current_time - self.last_check_time < self.cache_duration:
            return self.last_result
        
        # Try to reach OpenAI API
        try:
            import requests
            response = requests.head("https://api.openai.com", timeout=3)
            self.last_result = response.status_code < 500
        except Exception:
            self.last_result = False
        
        self.last_check_time = current_time
        logger.info(f"Internet check: {'available' if self.last_result else 'unavailable'}")
        return self.last_result
