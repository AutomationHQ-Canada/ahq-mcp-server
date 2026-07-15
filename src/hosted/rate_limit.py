import time

_PRUNE_AFTER_SECONDS = 600
_PRUNE_AT_SIZE = 10_000


class OrgRateLimiter:
    """
    Per-organization token bucket, in-process. No lock needed: allow() runs on the single
    asyncio event loop and never awaits. Per-POD, so N replicas multiply the effective ceiling
    by N — acceptable for v1 since the gateway has no rate limiting at all today (verified
    2026-07-14); this is strictly additive protection.
    """

    def __init__(self, per_minute: int, now=time.monotonic):
        self.capacity = float(per_minute)
        self.refill_per_second = per_minute / 60.0
        self._now = now
        self._buckets: dict[str, tuple[float, float]] = {}  # org_id -> (tokens, last_ts)

    def allow(self, org_id: str) -> bool:
        now = self._now()
        tokens, last = self._buckets.get(org_id, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_second)
        if len(self._buckets) >= _PRUNE_AT_SIZE:
            self._prune(now)
        if tokens >= 1.0:
            self._buckets[org_id] = (tokens - 1.0, now)
            return True
        self._buckets[org_id] = (tokens, now)
        return False

    def _prune(self, now: float) -> None:
        stale = [org for org, (_, last) in self._buckets.items() if now - last > _PRUNE_AFTER_SECONDS]
        for org in stale:
            del self._buckets[org]
