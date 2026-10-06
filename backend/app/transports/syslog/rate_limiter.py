import asyncio
import time


class SyslogRateLimiter:
    """Simple per-process rate limiter for syslog sends."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_send_at: dict[str, float] = {}

    async def wait(self, key: str, rate_per_second: float | None) -> None:
        if rate_per_second is None or rate_per_second <= 0:
            return

        min_interval = 1.0 / rate_per_second
        async with self._locks.setdefault(key, asyncio.Lock()):
            now = time.monotonic()
            last = self._last_send_at.get(key, 0.0)
            delay = min_interval - (now - last)
            if delay > 0:
                await asyncio.sleep(delay)
                now = time.monotonic()
            self._last_send_at[key] = now
