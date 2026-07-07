"""Rate limiter middleware."""

import time
from fastapi import Request
from fastapi.responses import JSONResponse


class RateLimiter:
    def __init__(self, requests_per_second: float = 10.0):
        self.requests_per_second = requests_per_second
        self._requests: dict[str, list[float]] = {}
        self._cleanup_interval = 60
        self._last_cleanup = time.time()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup(now)

        if client_ip not in self._requests:
            self._requests[client_ip] = []

        window_start = now - 1.0
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > window_start]

        if len(self._requests[client_ip]) >= self.requests_per_second:
            return False

        self._requests[client_ip].append(now)
        return True

    def _cleanup(self, now: float):
        cutoff = now - 60
        self._requests = {ip: times for ip, times in self._requests.items() if times and times[-1] > cutoff}
        self._last_cleanup = now


rate_limiter = RateLimiter(requests_per_second=10.0)
rate_limiter_scrape = RateLimiter(requests_per_second=0.5)


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"

    if request.url.path == "/api/scrape/trigger":
        if not rate_limiter_scrape.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "2"},
            )
    else:
        if not rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "1"},
            )

    response = await call_next(request)
    return response


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
