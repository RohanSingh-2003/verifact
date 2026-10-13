"""In-memory sliding-window API rate limiting middleware for VeriFact.

Enforces route-specific rate limits per client IP using a monotonic clock:
- POST /api/detect: 10 req/min (configurable via settings.rate_limit_detect_per_minute)
- POST /api/evaluations/run: 5 req/min (configurable via settings.rate_limit_batch_per_minute)
- POST /api/experiments/run: 5 req/min (configurable via settings.rate_limit_batch_per_minute)
- Default / other API requests (e.g. GET /api/runs/{id}, /api/health): 120 req/min
  (configurable via settings.rate_limit_default_per_minute)

Architecture & Operational Scope:
- Single-process scope: This rate limiter operates strictly in-memory within the
  current Python runtime process. It does NOT coordinate rate limits across multiple
  Uvicorn worker processes or distributed server instances. For multi-worker or
  distributed production topologies, rate limiting should be delegated to an external
  reverse proxy (such as Nginx/Cloudflare) or a centralized distributed cache (e.g. Redis).
- Concurrency & Thread-safety: In-memory state is protected with a re-entrant or standard
  mutual exclusion lock (threading.Lock) to ensure safe access from asynchronous task
  threads and concurrent request workers within the process.
- Clock: Uses time.monotonic() to prevent skew from NTP synchronization or system clock
  adjustments.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from app.config import Settings

TIER_DETECT = "detect"
TIER_BATCH = "batch"
TIER_EVALUATIONS_RUN = "evaluations_run"
TIER_EXPERIMENTS_RUN = "experiments_run"
TIER_DEFAULT = "default"


class RateLimiter:
    """Thread-safe in-memory sliding-window rate limiter."""

    def __init__(
        self,
        window_seconds: float = 60.0,
        cleanup_interval_seconds: float = 60.0,
        enabled: bool | None = None,
    ) -> None:
        self.window_seconds = window_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._enabled = enabled
        self._lock = threading.Lock()
        self._records: dict[str, list[float]] = {}
        self._last_cleanup: float = time.monotonic()

    def is_enabled(self, settings: Settings) -> bool:
        """Check whether rate limiting is active."""
        if self._enabled is not None:
            return self._enabled
        return settings.rate_limit_enabled

    def set_enabled(self, enabled: bool | None) -> None:
        """Override rate limiting state (True, False, or None to follow settings)."""
        self._enabled = enabled

    def reset(self) -> None:
        """Clear all in-memory records and reset cleanup timestamp."""
        with self._lock:
            self._records.clear()
            self._last_cleanup = time.monotonic()

    @staticmethod
    def resolve_tier(method: str, path: str) -> str:
        """Resolve route tier based on exact HTTP method and normalized path."""
        norm_method = method.upper()
        norm_path = path.rstrip("/") or "/"

        if norm_method == "POST":
            if norm_path == "/api/detect":
                return TIER_DETECT
            if norm_path == "/api/evaluations/run":
                return TIER_EVALUATIONS_RUN
            if norm_path == "/api/experiments/run":
                return TIER_EXPERIMENTS_RUN

        return TIER_DEFAULT

    @staticmethod
    def get_limit(tier: str, settings: Settings) -> int:
        """Get the configured limit for a route tier."""
        if tier == TIER_DETECT:
            return settings.rate_limit_detect_per_minute
        if tier in (TIER_EVALUATIONS_RUN, TIER_EXPERIMENTS_RUN):
            return settings.rate_limit_batch_per_minute
        return settings.rate_limit_default_per_minute

    @staticmethod
    def get_client_ip(
        request: Request,
        trusted_proxies: list[str] | set[str] | None = None,
    ) -> str:
        """Extract client IP, honoring X-Forwarded-For only when the immediate peer is a trusted proxy."""
        peer_ip = "127.0.0.1"
        if request.client and request.client.host:
            peer_ip = request.client.host.strip()

        if not trusted_proxies:
            return peer_ip

        trusted_set = {p.strip() for p in trusted_proxies if p.strip()}
        if peer_ip in trusted_set:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                parts = [p.strip() for p in forwarded.split(",") if p.strip()]
                if parts:
                    return parts[0]

        return peer_ip

    def acquire(
        self,
        client_ip: str,
        tier: str,
        limit: int,
        now: float | None = None,
    ) -> tuple[bool, int, int, int]:
        """Attempt to acquire a request slot within the sliding window.

        Args:
            client_ip: Client identifier.
            tier: Route tier string.
            limit: Maximum requests allowed in the sliding window.
            now: Monotonic timestamp (defaults to time.monotonic()).

        Returns:
            tuple of (allowed, remaining, retry_after_seconds, reset_seconds)
        """
        if now is None:
            now = time.monotonic()

        key = f"{client_ip}:{tier}"

        with self._lock:
            # Perform periodic cleanup of inactive/expired records
            if (now - self._last_cleanup) >= self.cleanup_interval_seconds:
                self._cleanup_locked(now)

            timestamps = self._records.get(key, [])
            cutoff = now - self.window_seconds
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= limit:
                oldest = valid_timestamps[0]
                retry_after = max(1, math.ceil(self.window_seconds - (now - oldest)))
                self._records[key] = valid_timestamps
                return False, 0, retry_after, retry_after

            valid_timestamps.append(now)
            self._records[key] = valid_timestamps
            remaining = max(0, limit - len(valid_timestamps))
            oldest = valid_timestamps[0]
            reset_seconds = max(1, math.ceil(self.window_seconds - (now - oldest)))
            return True, remaining, 0, reset_seconds

    def cleanup_expired(self, now: float | None = None) -> int:
        """Purge expired entries from memory. Returns count of purged keys."""
        if now is None:
            now = time.monotonic()
        with self._lock:
            return self._cleanup_locked(now)

    def _cleanup_locked(self, now: float) -> int:
        cutoff = now - self.window_seconds
        removed_count = 0
        keys_to_delete: list[str] = []

        for key, timestamps in self._records.items():
            active = [t for t in timestamps if t > cutoff]
            if not active:
                keys_to_delete.append(key)
            else:
                self._records[key] = active

        for key in keys_to_delete:
            del self._records[key]
            removed_count += 1

        self._last_cleanup = now
        return removed_count


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware applying thread-safe in-memory rate limits."""

    def __init__(self, app, limiter: RateLimiter | None = None) -> None:
        super().__init__(app)
        self.limiter = limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Pass CORS preflight requests without rate limiting
        if request.method == "OPTIONS":
            return await call_next(request)

        from app.config import get_settings

        settings = get_settings()

        if not self.limiter.is_enabled(settings):
            return await call_next(request)

        client_ip = self.limiter.get_client_ip(request, settings.trusted_proxies)
        tier = self.limiter.resolve_tier(request.method, request.url.path)
        limit = self.limiter.get_limit(tier, settings)

        allowed, remaining, retry_after, reset_seconds = self.limiter.acquire(
            client_ip=client_ip,
            tier=tier,
            limit=limit,
        )

        if not allowed:
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(retry_after),
            }
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers=headers,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)
        return response
