"""Tests for VeriFact API rate limiting middleware and safe server binding."""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.middleware.rate_limit import RateLimiter


@pytest.fixture
def rate_limit_client() -> Generator[TestClient, None, None]:
    """TestClient with rate limiting enabled and clean isolated state."""
    limiter: RateLimiter = app.state.rate_limiter
    limiter.reset()
    limiter.set_enabled(True)
    client = TestClient(app)
    try:
        yield client
    finally:
        limiter.reset()
        limiter.set_enabled(None)


def test_detect_endpoint_rate_limit(rate_limit_client: TestClient) -> None:
    """POST /api/detect must enforce 10 req/min per client IP and return HTTP 429 with Retry-After."""
    payload = {"question": "What is the speed of light?"}

    # First 10 requests should succeed (not return 429)
    for i in range(10):
        resp = rate_limit_client.post("/api/detect", json=payload)
        assert resp.status_code != 429, f"Request {i + 1} was unexpectedly rate-limited"
        assert resp.headers.get("X-RateLimit-Limit") == "10"
        expected_remaining = str(9 - i)
        assert resp.headers.get("X-RateLimit-Remaining") == expected_remaining
        assert "X-RateLimit-Reset" in resp.headers

    # 11th request must return HTTP 429
    resp_blocked = rate_limit_client.post("/api/detect", json=payload)
    assert resp_blocked.status_code == 429
    assert resp_blocked.headers.get("X-RateLimit-Limit") == "10"
    assert resp_blocked.headers.get("X-RateLimit-Remaining") == "0"
    assert "Retry-After" in resp_blocked.headers
    retry_after = int(resp_blocked.headers["Retry-After"])
    assert 1 <= retry_after <= 60
    assert resp_blocked.json() == {
        "detail": "Too many requests. Please try again later."
    }


def test_evaluations_run_endpoint_rate_limit(rate_limit_client: TestClient) -> None:
    """POST /api/evaluations/run must enforce 5 req/min per client IP."""
    payload = {"dataset_name": "pilot", "max_questions": 1}

    for i in range(5):
        resp = rate_limit_client.post("/api/evaluations/run", json=payload)
        assert resp.status_code != 429, (
            f"Evaluation request {i + 1} was unexpectedly rate-limited"
        )
        assert resp.headers.get("X-RateLimit-Limit") == "5"

    resp_blocked = rate_limit_client.post("/api/evaluations/run", json=payload)
    assert resp_blocked.status_code == 429
    assert resp_blocked.headers.get("Retry-After") is not None
    assert resp_blocked.headers.get("X-RateLimit-Limit") == "5"
    assert resp_blocked.headers.get("X-RateLimit-Remaining") == "0"


def test_experiments_run_endpoint_rate_limit(rate_limit_client: TestClient) -> None:
    """POST /api/experiments/run must enforce 5 req/min per client IP."""
    payload = {
        "dataset_name": "pilot",
        "max_questions": 1,
        "generator_models": ["gemma4:26b"],
        "verifier_models": ["gemini-3.8-flash"],
    }

    for i in range(5):
        resp = rate_limit_client.post("/api/experiments/run", json=payload)
        assert resp.status_code != 429, (
            f"Experiment request {i + 1} was unexpectedly rate-limited"
        )
        assert resp.headers.get("X-RateLimit-Limit") == "5"

    resp_blocked = rate_limit_client.post("/api/experiments/run", json=payload)
    assert resp_blocked.status_code == 429
    assert resp_blocked.headers.get("Retry-After") is not None
    assert resp_blocked.headers.get("X-RateLimit-Limit") == "5"


def test_polling_requests_remain_below_default_limit(
    rate_limit_client: TestClient,
) -> None:
    """GET /api/runs/{id} and health polling must have 120 req/min and stay unblocked during regular polling."""
    for i in range(25):
        resp = rate_limit_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-RateLimit-Limit") == "120"
        assert int(resp.headers.get("X-RateLimit-Remaining", "0")) == 120 - (i + 1)

    poll_resp = rate_limit_client.get("/api/runs/non-existent-run-id")
    assert poll_resp.status_code == 404  # Valid API routing, not 429
    assert poll_resp.headers.get("X-RateLimit-Limit") == "120"


def test_window_expiration_with_mocked_monotonic_clock(
    rate_limit_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Old entries must expire after 60 seconds using monotonic clock."""
    current_time = 1000.0

    def mock_monotonic() -> float:
        return current_time

    monkeypatch.setattr(time, "monotonic", mock_monotonic)

    payload = {"question": "What is the speed of light?"}

    # Consume all 10 slots at t=1000.0
    for _ in range(10):
        resp = rate_limit_client.post("/api/detect", json=payload)
        assert resp.status_code != 429

    # 11th request is blocked
    blocked = rate_limit_client.post("/api/detect", json=payload)
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "60"

    # Advance clock by 30 seconds: still blocked, Retry-After should decrease to 30
    current_time = 1030.0
    still_blocked = rate_limit_client.post("/api/detect", json=payload)
    assert still_blocked.status_code == 429
    assert still_blocked.headers.get("Retry-After") == "30"

    # Advance clock beyond 60-second window (t=1061.0): window has expired
    current_time = 1061.0
    allowed = rate_limit_client.post("/api/detect", json=payload)
    assert allowed.status_code != 429
    assert allowed.headers.get("X-RateLimit-Limit") == "10"
    assert allowed.headers.get("X-RateLimit-Remaining") == "9"


def test_untrusted_forwarded_ip_not_bypassing_limits(
    rate_limit_client: TestClient,
) -> None:
    """Untrusted clients sending X-Forwarded-For must NOT bypass rate limits."""
    # Ensure trusted_proxies is empty (default configuration)
    payload = {"question": "What is water made of?"}

    # Send 10 requests, each trying to forge a different client IP via X-Forwarded-For
    for i in range(10):
        headers = {"X-Forwarded-For": f"198.51.100.{i + 1}"}
        resp = rate_limit_client.post("/api/detect", json=payload, headers=headers)
        assert resp.status_code != 429

    # 11th request with yet another spoofed IP must STILL be rate limited
    headers = {"X-Forwarded-For": "198.51.100.99"}
    blocked = rate_limit_client.post("/api/detect", json=payload, headers=headers)
    assert blocked.status_code == 429


def test_trusted_proxy_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    """When peer is a trusted proxy, X-Forwarded-For is respected to identify separate clients."""
    limiter: RateLimiter = app.state.rate_limiter
    limiter.reset()
    limiter.set_enabled(True)

    # Configure testclient host as trusted proxy
    settings = get_settings()
    monkeypatch.setattr(settings, "trusted_proxies", ["testclient"])

    client = TestClient(app)
    payload = {"question": "What is nitrogen?"}

    try:
        # Client A makes 10 requests through the trusted proxy
        headers_a = {"X-Forwarded-For": "203.0.113.10"}
        for _ in range(10):
            resp = client.post("/api/detect", json=payload, headers=headers_a)
            assert resp.status_code != 429

        # Client A's 11th request is blocked
        blocked_a = client.post("/api/detect", json=payload, headers=headers_a)
        assert blocked_a.status_code == 429

        # Client B makes requests through the same trusted proxy and is NOT blocked
        headers_b = {"X-Forwarded-For": "203.0.113.20"}
        resp_b = client.post("/api/detect", json=payload, headers=headers_b)
        assert resp_b.status_code != 429
        assert resp_b.headers.get("X-RateLimit-Remaining") == "9"
    finally:
        limiter.reset()
        limiter.set_enabled(None)


def test_cleanup_of_expired_client_records() -> None:
    """RateLimiter.cleanup_expired() must purge inactive records and prevent unbounded growth."""
    limiter = RateLimiter(window_seconds=60.0, cleanup_interval_seconds=60.0)

    # Add 5 client records at t=100.0
    for i in range(5):
        allowed, _, _, _ = limiter.acquire(f"client-{i}", "detect", 10, now=100.0)
        assert allowed is True

    assert len(limiter._records) == 5

    # Cleanup at t=120.0 (within window): 0 records purged
    purged = limiter.cleanup_expired(now=120.0)
    assert purged == 0
    assert len(limiter._records) == 5

    # Cleanup at t=161.0 (after window expiration): all 5 records purged
    purged = limiter.cleanup_expired(now=161.0)
    assert purged == 5
    assert len(limiter._records) == 0


def test_rate_limit_disabled_programmatically(rate_limit_client: TestClient) -> None:
    """Disabling rate limiting programmatically allows requests to exceed limits without 429."""
    app.state.rate_limiter.set_enabled(False)
    payload = {"question": "What is hydrogen?"}

    for _ in range(15):
        resp = rate_limit_client.post("/api/detect", json=payload)
        assert resp.status_code != 429
        # Headers should not be attached when disabled
        assert "X-RateLimit-Limit" not in resp.headers


def test_rate_limit_disabled_via_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting rate_limit_enabled=False in settings disables the middleware."""
    limiter: RateLimiter = app.state.rate_limiter
    limiter.reset()
    limiter.set_enabled(None)  # Follow settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    client = TestClient(app)
    payload = {"question": "What is helium?"}

    for _ in range(15):
        resp = client.post("/api/detect", json=payload)
        assert resp.status_code != 429


def test_options_cors_preflight_bypasses_limiter(rate_limit_client: TestClient) -> None:
    """OPTIONS preflight requests must bypass rate limiting."""
    for _ in range(15):
        resp = rate_limit_client.options("/api/detect")
        assert resp.status_code in (200, 204, 405)
        assert resp.status_code != 429


def test_thread_safety_concurrent_access() -> None:
    """Concurrent threads acquiring slots must not exceed the limit or corrupt state."""
    limiter = RateLimiter(window_seconds=60.0)
    limit = 20
    client_ip = "192.168.1.100"
    tier = "detect"
    now = time.monotonic()

    results: list[bool] = []

    def worker() -> bool:
        allowed, _, _, _ = limiter.acquire(client_ip, tier, limit, now=now)
        return allowed

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker) for _ in range(50)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Exactly `limit` attempts must succeed
    assert results.count(True) == limit
    assert results.count(False) == 30
    assert len(limiter._records[f"{client_ip}:{tier}"]) == limit


def test_server_binding_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should provide safe default server binding and custom port support."""
    monkeypatch.delenv("RATE_LIMIT_ENABLED", raising=False)
    default_settings = Settings()
    assert default_settings.server_host == "127.0.0.1"
    assert default_settings.server_port == 8000
    assert default_settings.rate_limit_enabled is True
    assert default_settings.rate_limit_detect_per_minute == 10
    assert default_settings.rate_limit_batch_per_minute == 5
    assert default_settings.rate_limit_default_per_minute == 120
    assert default_settings.trusted_proxies == []


def test_trusted_proxies_parsing_formats() -> None:
    """Settings should handle comma-separated string, JSON, and list formats for trusted_proxies."""
    s1 = Settings(trusted_proxies="127.0.0.1, 10.0.0.1")
    assert s1.trusted_proxies == ["127.0.0.1", "10.0.0.1"]

    s2 = Settings(trusted_proxies='["192.168.1.1", "10.0.0.2"]')
    assert s2.trusted_proxies == ["192.168.1.1", "10.0.0.2"]

    s3 = Settings(trusted_proxies=["172.16.0.1"])
    assert s3.trusted_proxies == ["172.16.0.1"]

    s4 = Settings(trusted_proxies="")
    assert s4.trusted_proxies == []
