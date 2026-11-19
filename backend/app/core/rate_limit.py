import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """In-memory per-IP sliding-window rate limiter to mitigate credential brute-force attacks."""

    def __init__(self, max_requests: int = 15, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        self._hits.clear()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts. Please try again shortly.",
                headers={"Retry-After": str(self.window_seconds)},
            )
        bucket.append(now)


login_rate_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60)


async def enforce_login_rate_limit(request: Request) -> None:
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    login_rate_limiter.check(client_ip)
