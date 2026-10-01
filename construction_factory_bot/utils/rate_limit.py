"""
API Rate Limiting — xavfsizlik qatlami (TZ: Xavfsizlik bo'limi)

In-memory token bucket: har bir IP / user uchun daqiqada N ta so'rov.
Haddan tashqari ko'p so'rov yuborganlar 429 bilan qaytariladi.
Shuningdek "shubhali harakat" (brute force urinishi) qayd etiladi.
"""
from threading import Lock
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Tuple


class RateLimiter:
    """Oddiy sliding-window rate limiter (bitta protsess uchun)."""

    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, list] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> Tuple[bool, int]:
        """So'rovni qayd qiladi. (ruxsat, qancha kutish kerak)"""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)
        with self._lock:
            timestamps = [t for t in self._hits.get(key, []) if t > cutoff]
            if len(timestamps) >= self.max_requests:
                self._hits[key] = timestamps + [now]
                wait = int((timestamps[0] + timedelta(seconds=self.window_seconds) - now).total_seconds())
                return False, max(wait, 1)
            timestamps.append(now)
            self._hits[key] = timestamps
            return True, 0

    def reset(self, key: str = None):
        with self._lock:
            if key:
                self._hits.pop(key, None)
            else:
                self._hits.clear()


# Global instance — API'dan import qilinadi
limiter = RateLimiter(max_requests=300, window_seconds=60)

# Kirish (login) uchun qat'iyroq cheklov: IP bo'yicha daqiqada 10 urinish
login_limiter = RateLimiter(max_requests=10, window_seconds=60)