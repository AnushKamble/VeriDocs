"""
Conservative token-bucket rate limiter for SEC EDGAR requests.
"""

import asyncio
import time
from typing import Optional


class SECRateLimiter:
    """
    Asynchronous token-bucket rate limiter enforcing requests per second strictly
    below the SEC fair-access limit (default <= 2.0 req/sec, SEC cap is 10.0 req/sec).
    """

    def __init__(self, requests_per_second: float = 2.0, max_burst: int = 1):
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be strictly positive")
        self.rate = requests_per_second
        self.capacity = float(max_burst)
        self.tokens = float(max_burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """
        Wait until a request token is available, returning elapsed wait time in seconds.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now

            # Replenish tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0

            # Calculate required sleep time to accumulate 1.0 token
            deficit = 1.0 - self.tokens
            wait_time = deficit / self.rate
            self.tokens = 0.0
            self.last_update = now + wait_time

        await asyncio.sleep(wait_time)
        return wait_time
