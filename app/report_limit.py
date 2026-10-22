"""Per-user report cooldown for the bot's single asyncio process."""

from math import ceil
from time import monotonic
from typing import Callable

DEFAULT_REPORT_COOLDOWN_SECONDS = 300


class ReportRateLimit:
    def __init__(self, cooldown_seconds=DEFAULT_REPORT_COOLDOWN_SECONDS,
                 *, clock: Callable[[], float] = monotonic):
        if (isinstance(cooldown_seconds, bool) or not isinstance(cooldown_seconds, (int, str))
                or not str(cooldown_seconds).isascii() or not str(cooldown_seconds).isdigit()
                or int(cooldown_seconds) <= 0):
            raise ValueError('REPORT_COOLDOWN_SECONDS must be a positive integer')
        self.cooldown_seconds = int(cooldown_seconds)
        self.clock = clock
        self.deadlines = {}
        self.in_flight = set()

    def acquire(self, user_id: int) -> int:
        """Reserve synchronously before any await; return retry seconds or zero."""
        now = self.clock()
        expired = [key for key, deadline in self.deadlines.items()
                   if deadline <= now and key not in self.in_flight]
        for key in expired:
            del self.deadlines[key]
        if user_id in self.deadlines:
            return max(1, ceil(self.deadlines[user_id] - now))
        self.deadlines[user_id] = now + self.cooldown_seconds
        self.in_flight.add(user_id)
        return 0

    def finish(self, user_id: int, success: bool):
        self.in_flight.discard(user_id)
        if not success:
            self.deadlines.pop(user_id, None)
