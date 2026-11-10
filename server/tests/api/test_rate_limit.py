import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import rate_limit as rl
from app.core.encryption import encrypt
from app.core.security import hash_password, make_token
from app.db.models import Tenant, User
from app.db.session import engine_owner
from app.main import app

PASSWORD = "correct-horse-1"


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def login_user():
    """One tenant with one user who has a password and an authenticator. Yields a dict."""
    tid, uid = uuid.uuid4(), uuid.uuid4()
    email = f"rl-{uuid.uuid4().hex[:10]}@example.test"
    secret = pyotp.random_base32()
    with Session(engine_owner) as s:
        s.add(Tenant(id=tid, name="RL Tenant"))
        s.flush()
        s.add(User(
            id=uid, tenant_id=tid, email=email, name="RL User", role="salesperson",
            password_hash=hash_password(PASSWORD), mfa_secret=encrypt(secret),
        ))
        s.commit()
    yield {"tid": tid, "uid": uid, "email": email, "secret": secret}
    with engine_owner.begin() as conn:
        for table in ("audit_log", "users"):
            conn.execute(text(f"DELETE FROM {table} WHERE tenant_id = :t"), {"t": tid})
        conn.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_wrong_passwords_lock_the_email(client, login_user):
    for _ in range(rl.LOGIN_EMAIL_LIMIT):
        assert _login(client, login_user["email"], "wrong-password-1").status_code == 401
    locked = _login(client, login_user["email"], "wrong-password-1")
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) > 0
    # Even the correct password is refused while locked.
    assert _login(client, login_user["email"], PASSWORD).status_code == 429


def test_successful_login_resets_the_counter(client, login_user):
    for _ in range(rl.LOGIN_EMAIL_LIMIT - 1):
        assert _login(client, login_user["email"], "wrong-password-1").status_code == 401
    assert _login(client, login_user["email"], PASSWORD).status_code == 200
    # The counter started again, so the full number of failures is allowed once more.
    for _ in range(rl.LOGIN_EMAIL_LIMIT - 1):
        assert _login(client, login_user["email"], "wrong-password-1").status_code == 401


def test_one_address_trying_many_emails_gets_locked(client):
    for i in range(rl.LOGIN_IP_LIMIT):
        r = _login(client, f"nobody{i}-{uuid.uuid4().hex[:6]}@example.test", "wrong-password-1")
        assert r.status_code == 401
    r = _login(client, f"nobody-last-{uuid.uuid4().hex[:6]}@example.test", "wrong-password-1")
    assert r.status_code == 429


def test_wrong_codes_lock_the_user(client, login_user):
    token = make_token("challenge", login_user["uid"], login_user["tid"], 5)
    now_code = pyotp.TOTP(login_user["secret"]).now()
    wrong = f"{(int(now_code) + 1) % 1_000_000:06d}"
    for _ in range(rl.MFA_USER_LIMIT):
        r = client.post("/auth/mfa/verify", json={"challenge_token": token, "code": wrong})
        assert r.status_code == 401 and r.json()["detail"] == "invalid code"
    r = client.post("/auth/mfa/verify", json={"challenge_token": token, "code": wrong})
    assert r.status_code == 429
    # The right code is refused too while locked.
    r = client.post("/auth/mfa/verify", json={"challenge_token": token, "code": now_code})
    assert r.status_code == 429