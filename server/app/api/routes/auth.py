import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text

from app.api.deps import CurrentUser, current_user
from app.config import settings
from app.core.audit import audit
from app.core.encryption import decrypt, encrypt
from app.core.rate_limit import (
    LOGIN_EMAIL_LIMIT, LOGIN_IP_LIMIT, MFA_USER_LIMIT, PASSWORD_USER_LIMIT,
    client_ip, enforce, record_failure, reset, rl_key,
)
from app.core.security import (
    hash_password, make_token, new_totp_secret, read_token, totp_uri, verify_password, verify_totp,
)
from app.core.tenancy import tenant_session
from app.db.models import Tenant, User
from app.db.session import SessionApp
from app.schemas.auth import ConfirmIn, EnrollIn, LoginIn, MfaVerifyIn, PasswordChangeIn

router = APIRouter(tags=["auth"])

_BAD_LOGIN = "invalid email or password"


def _tenant_name(s, tenant_id: uuid.UUID) -> str | None:
    return s.execute(select(Tenant.name).where(Tenant.id == tenant_id)).scalar_one_or_none()


def _user_dict(u: User, tenant_name: str | None) -> dict:
    return {
        "id": str(u.id),
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "tenant_name": tenant_name,
    }


def _session_response(s, u: User) -> dict:
    token = make_token("access", u.id, u.tenant_id, settings.access_token_minutes, role=u.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
        "user": _user_dict(u, _tenant_name(s, u.tenant_id)),
    }


def _challenge(token: str, kind: str = "challenge") -> tuple[uuid.UUID, uuid.UUID, dict]:
    payload = read_token(token, kind)
    if payload is None:
        raise HTTPException(401, "invalid or expired token, please log in again")
    try:
        return uuid.UUID(payload["sub"]), uuid.UUID(payload["tid"]), payload
    except (KeyError, ValueError):
        raise HTTPException(401, "invalid token")


@router.post("/login")
def login(body: LoginIn, request: Request):
    """Step 1: password. Returns a short-lived challenge, not a session."""
    email_key = rl_key("login-email", body.email)
    ip_key = rl_key("login-ip", client_ip(request))
    enforce((email_key, LOGIN_EMAIL_LIMIT), (ip_key, LOGIN_IP_LIMIT))

    with SessionApp() as s:
        row = s.execute(text("SELECT * FROM login_lookup(:e)"), {"e": body.email}).first()
    ok = verify_password(body.password, row.password_hash if row else None)
    if row is None or not ok or not row.active:
        record_failure(email_key, LOGIN_EMAIL_LIMIT)
        record_failure(ip_key, LOGIN_IP_LIMIT)
        if row is not None:
            with tenant_session(row.tenant_id) as s:
                audit(s, row.tenant_id, str(row.user_id), "login_failed")
        raise HTTPException(401, _BAD_LOGIN)
    reset(email_key)
    return {
        "challenge_token": make_token("challenge", row.user_id, row.tenant_id, 5),
        "mfa_enrolled": bool(row.has_mfa),
    }


@router.post("/mfa/verify")
def mfa_verify(body: MfaVerifyIn):
    """Step 2 for enrolled users: the 6-digit code from their authenticator app."""
    uid, tid, _ = _challenge(body.challenge_token)
    mfa_key = rl_key("mfa-user", str(uid))
    enforce((mfa_key, MFA_USER_LIMIT))
    with tenant_session(tid) as s:
        u = s.execute(select(User).where(User.id == uid, User.tenant_id == tid)).scalar_one_or_none()
        if u is None or not u.active or not u.mfa_secret:
            raise HTTPException(401, _BAD_LOGIN)
        if not verify_totp(decrypt(u.mfa_secret), body.code):
            audit(s, tid, str(uid), "mfa_failed")
            # Raising would roll the audit entry back, so commit it by returning instead.
            failed = True
        else:
            audit(s, tid, str(uid), "login")
            failed = False
        response = None if failed else _session_response(s, u)
    if failed:
        record_failure(mfa_key, MFA_USER_LIMIT)
        raise HTTPException(401, "invalid code")
    reset(mfa_key)
    return response


@router.post("/mfa/enroll")
def mfa_enroll(body: EnrollIn):
    """First login: start setting up an authenticator app. Nothing is saved until confirmed."""
    uid, tid, _ = _challenge(body.challenge_token)
    with tenant_session(tid) as s:
        u = s.execute(select(User).where(User.id == uid, User.tenant_id == tid)).scalar_one_or_none()
        if u is None or not u.active:
            raise HTTPException(401, _BAD_LOGIN)
        if u.mfa_secret:
            raise HTTPException(409, "MFA is already set up")
        email = u.email
    secret = new_totp_secret()
    return {
        "enroll_token": make_token("enroll", uid, tid, 10, secret=secret),
        "secret": secret,
        "otpauth_uri": totp_uri(secret, email),
    }


@router.post("/mfa/confirm")
def mfa_confirm(body: ConfirmIn):
    uid, tid, payload = _challenge(body.enroll_token, "enroll")
    mfa_key = rl_key("mfa-user", str(uid))
    enforce((mfa_key, MFA_USER_LIMIT))
    secret = payload.get("secret")
    if not secret or not verify_totp(secret, body.code):
        record_failure(mfa_key, MFA_USER_LIMIT)
        raise HTTPException(401, "invalid code")
    with tenant_session(tid) as s:
        u = s.execute(select(User).where(User.id == uid, User.tenant_id == tid)).scalar_one_or_none()
        if u is None or not u.active:
            raise HTTPException(401, _BAD_LOGIN)
        if u.mfa_secret:
            raise HTTPException(409, "MFA is already set up")
        u.mfa_secret = encrypt(secret)  # stored encrypted
        audit(s, tid, str(uid), "mfa_enrolled")
        response = _session_response(s, u)
    reset(mfa_key)
    return response


@router.get("/me")
def me(user: CurrentUser = Depends(current_user)):
    with tenant_session(user.tenant_id) as s:
        tenant_name = _tenant_name(s, user.tenant_id)
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "tenant_name": tenant_name,
    }


@router.post("/change-password")
def change_password(body: PasswordChangeIn, user: CurrentUser = Depends(current_user)):
    pw_key = rl_key("password-user", str(user.id))
    enforce((pw_key, PASSWORD_USER_LIMIT))
    try:
        new_hash = hash_password(body.new_password)
    except ValueError as e:
        raise HTTPException(422, str(e))
    with tenant_session(user.tenant_id) as s:
        u = s.execute(select(User).where(User.id == user.id, User.tenant_id == user.tenant_id)).scalar_one()
        wrong = not verify_password(body.old_password, u.password_hash)
        if not wrong:
            u.password_hash = new_hash
            audit(s, user.tenant_id, str(user.id), "password_changed")
    if wrong:
        record_failure(pw_key, PASSWORD_USER_LIMIT)
        raise HTTPException(400, "current password is wrong")
    reset(pw_key)
    return {"ok": True}