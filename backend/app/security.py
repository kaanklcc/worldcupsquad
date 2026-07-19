"""Small, dependency-free security controls for the public hackathon API.

The limiter is intentionally process-local.  It protects the single-instance
demo from brute force and API-credit exhaustion; a multi-instance deployment
should replace it with a shared Redis-backed limiter.
"""
from __future__ import annotations

from collections import defaultdict, deque
from hashlib import sha256
import hmac
import math
import threading
import time
from typing import Deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, math.ceil(events[0] + window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)

            # Keep attacker-controlled identifiers from growing memory forever.
            if len(self._events) > 10_000:
                stale = [name for name, values in self._events.items() if not values or values[-1] <= cutoff]
                for name in stale[:2_000]:
                    self._events.pop(name, None)
                # A distributed identifier spray can keep every entry fresh.
                # Bound memory even in that case; losing the oldest limiter
                # buckets is safer than allowing unbounded process growth.
                if len(self._events) > 10_000:
                    oldest = sorted(
                        self._events,
                        key=lambda name: self._events[name][-1] if self._events[name] else float("-inf"),
                    )
                    for name in oldest:
                        if len(self._events) <= 10_000:
                            break
                        if name != key:
                            self._events.pop(name, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


rate_limiter = SlidingWindowLimiter()


def request_ip(request: Request) -> str:
    """Use the socket peer, not spoofable forwarding headers."""
    return request.client.host if request.client else "unknown"


def rate_limit(
    request: Request,
    scope: str,
    *,
    limit: int,
    window_seconds: int,
    subject: str = "",
) -> None:
    subject_digest = sha256(subject.strip().lower().encode("utf-8")).hexdigest()[:20] if subject else "-"
    rate_limiter.check(
        f"{scope}:{request_ip(request)}:{subject_digest}",
        limit=limit,
        window_seconds=window_seconds,
    )


def require_csrf(request: Request, cookie_name: str) -> None:
    """Double-submit CSRF protection for cookie-authenticated mutations."""
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(cookie_name, "")
    header = request.headers.get("X-CSRF-Token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="CSRF validation failed. Refresh the page and try again.")
