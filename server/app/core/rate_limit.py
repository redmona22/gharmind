"""Login rate limiting, kept in Redis.

Counts FAILED attempts only. Reaching the limit locks that key for LOCKOUT seconds, and a
successful login clears the counter. If Redis is down the limiter lets requests through
(and logs a warning), so a Redis outage cannot lock every user out of the dashboard.
"""
import hashlib
import logging
import math

from fastapi import HTTPException, Request

from app.config import settings

log = logging.getLogger(__name__)

WINDOW = 15 * 60  # seconds over which failures are counted
LOCKOUT = 15 * 60  # seconds a key stays locked once its limit is reached

LOGIN_EMAIL_LIMIT = 10  # wrong passwords per email
LOGIN_IP_LIMIT = 30  # failed logins per address
MFA_USER_LIMIT = 5  # wrong 6-digit codes per user
PASSWORD_USER_LIMIT = 5  # wrong "current password" entries per user

_store = None  # a redis client; tests replace it with an in-memory fake


def _get_store():
    global _store
    if _store is None:
        import redis

        _store = redis.Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
        )
    return _store


def rl_key(scope: str, ident: str) -> str:
    """Counter name. The identifier is hashed so no email address is stored in Redis."""
    return f"rl:{scope}:{hashlib.sha256(ident.encode()).hexdigest()[:32]}"


def client_ip(request: Request) -> str:
    # Only trust X-Forwarded-For when the API sits behind your own proxy (TRUST_FORWARDED_FOR=true),
    # otherwise anyone could fake it.
    if settings.trust_forwarded_for:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def blocked_for(key: str, limit: int) -> int:
    """Seconds left on the lock, or 0 if the key is not locked."""
    try:
        store = _get_store()
        if int(store.get(key) or 0) < limit:
            return 0
        return max(int(store.ttl(key)), 1)
    except Exception:
        log.warning("rate limiter unavailable, letting the request through", exc_info=True)
        return 0


def record_failure(key: str, limit: int) -> None:
    try:
        store = _get_store()
        n = store.incr(key)
        if n == 1:
            store.expire(key, WINDOW)
        if n == limit:
            store.expire(key, LOCKOUT)  # the lock starts now
    except Exception:
        log.warning("rate limiter unavailable, failure not counted", exc_info=True)


def reset(key: str) -> None:
    try:
        _get_store().delete(key)
    except Exception:
        log.warning("rate limiter unavailable, counter not cleared", exc_info=True)


def enforce(*checks: tuple[str, int]) -> None:
    """Raise 429 if any (key, limit) pair is locked."""
    wait = max((blocked_for(key, limit) for key, limit in checks), default=0)
    if wait:
        minutes = math.ceil(wait / 60)
        raise HTTPException(
            429,
            f"too many failed attempts, please try again in {minutes} minute(s)",
            headers={"Retry-After": str(wait)},
        )