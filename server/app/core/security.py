import time
import uuid

import bcrypt
import pyotp
from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
MIN_PASSWORD = 10
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt())


def hash_password(password: str) -> str:
    raw = password.encode()
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
    if len(raw) > 72:
        raise ValueError("password must be at most 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    """Always does one bcrypt check, so a missing account takes as long as a wrong password."""
    try:
        ok = bcrypt.checkpw(password.encode(), hashed.encode() if hashed else _DUMMY_HASH)
    except ValueError:
        return False
    return bool(hashed) and ok


def make_token(kind: str, user_id: uuid.UUID, tenant_id: uuid.UUID, minutes: float, **extra) -> str:
    now = int(time.time())
    payload = {
        "typ": kind, "sub": str(user_id), "tid": str(tenant_id),
        "iat": now, "exp": now + int(minutes * 60), **extra,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def read_token(token: str, kind: str) -> dict | None:
    """Return the payload only if the signature, expiry and token type are all right."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
    return payload if payload.get("typ") == kind else None


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Gharmind")


def verify_totp(secret: str, code: str) -> bool:
    code = (code or "").strip()
    return code.isdigit() and pyotp.TOTP(secret).verify(code, valid_window=1)
