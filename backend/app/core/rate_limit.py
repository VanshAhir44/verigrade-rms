import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """Bounded in-memory per-IP sliding-window rate limiter with stale-key eviction."""

    def __init__(
        self,
        max_requests: int = 15,
        window_seconds: int = 60,
        max_tracked_keys: int = 10_000,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_tracked_keys = max_tracked_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        self._hits.clear()

    def _evict_expired(self, cutoff: float) -> None:
        empty_keys = []
        for k, dq in self._hits.items():
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if not dq:
                empty_keys.append(k)
        for k in empty_keys:
            self._hits.pop(k, None)

        # Hard cap to prevent memory exhaustion under spoofed/distributed IPs
        if len(self._hits) >= self.max_tracked_keys:
            oldest_keys = list(self._hits.keys())[: len(self._hits) - self.max_tracked_keys + 1]
            for k in oldest_keys:
                self._hits.pop(k, None)

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        if len(self._hits) >= self.max_tracked_keys:
            self._evict_expired(cutoff)

        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again shortly.",
                headers={"Retry-After": str(self.window_seconds)},
            )
        bucket.append(now)


def extract_client_ip(request: Request) -> str:
    """
    Uses request.client.host by default. When running behind a single trusted reverse proxy
    (TRUST_PROXY_HEADERS=true, e.g. Render), uses the rightmost X-Forwarded-For entry
    appended by the proxy rather than the client-spoofable leftmost value.
    """
    if os.getenv("TRUST_PROXY_HEADERS", "").lower() == "true":
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                return parts[-1]
    return request.client.host if request.client else "unknown"


login_rate_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60)
refresh_rate_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60)
verify_rate_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)


async def enforce_login_rate_limit(request: Request) -> None:
    login_rate_limiter.check(extract_client_ip(request))


async def enforce_refresh_rate_limit(request: Request) -> None:
    refresh_rate_limiter.check(extract_client_ip(request))


async def enforce_verify_rate_limit(request: Request) -> None:
    verify_rate_limiter.check(extract_client_ip(request))
