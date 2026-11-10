import pyotp
from sqlalchemy import text

from app.core.encryption import decrypt
from app.db.session import engine_owner
from tests.dashboard.helpers import PASSWORD, auth, login, make_person
from sqlalchemy.orm import Session


def test_wrong_password_and_unknown_email_look_identical(client, company):
    a = client.post("/auth/login", json={"email": company.admin.email, "password": "wrong-password-123"})
    b = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-123"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_full_login_with_authenticator_code(client, company):
    token = login(client, company.admin)
    r = client.get("/auth/me", headers=auth(token))
    assert r.status_code == 200 and r.json()["role"] == "admin"


def test_wrong_authenticator_code_is_rejected(client, company):
    r = client.post("/auth/login", json={"email": company.admin.email, "password": PASSWORD})
    ch = r.json()["challenge_token"]
    good = pyotp.TOTP(company.admin.secret).now()
    bad = "000000" if good != "000000" else "111111"
    assert client.post("/auth/mfa/verify", json={"challenge_token": ch, "code": bad}).status_code == 401


def test_a_challenge_token_is_not_a_session(client, company):
    ch = client.post("/auth/login", json={"email": company.admin.email, "password": PASSWORD}).json()["challenge_token"]
    assert client.get("/auth/me", headers=auth(ch)).status_code == 401


def test_endpoints_need_a_token(client, company):
    assert client.get("/leads").status_code == 401
    assert client.get("/listings").status_code == 401
    assert client.get("/auth/me", headers=auth("garbage")).status_code == 401


def test_first_login_sets_up_mfa_and_stores_the_secret_encrypted(client, company):
    with Session(engine_owner) as s:
        newbie = make_person(s, company.tenant_id, "salesperson", with_mfa=False)
        s.commit()
    r = client.post("/auth/login", json={"email": newbie.email, "password": PASSWORD})
    assert r.json()["mfa_enrolled"] is False
    challenge = r.json()["challenge_token"]

    e = client.post("/auth/mfa/enroll", json={"challenge_token": challenge})
    assert e.status_code == 200
    secret = e.json()["secret"]
    assert e.json()["otpauth_uri"].startswith("otpauth://totp/")

    # a wrong code does not complete setup
    assert client.post("/auth/mfa/confirm", json={"enroll_token": e.json()["enroll_token"], "code": "abcdef"}).status_code in (401, 422)

    c = client.post("/auth/mfa/confirm", json={
        "enroll_token": e.json()["enroll_token"], "code": pyotp.TOTP(secret).now()})
    assert c.status_code == 200 and c.json()["access_token"]

    with engine_owner.connect() as conn:
        stored = conn.execute(text("SELECT mfa_secret FROM users WHERE id = :i"), {"i": newbie.id}).scalar()
    assert stored != secret and decrypt(stored) == secret

    # enrolling again is refused
    again = client.post("/auth/login", json={"email": newbie.email, "password": PASSWORD}).json()["challenge_token"]
    assert client.post("/auth/mfa/enroll", json={"challenge_token": again}).status_code == 409


def test_deactivated_user_loses_access_immediately(client, company):
    token = login(client, company.sales1)
    assert client.get("/auth/me", headers=auth(token)).status_code == 200
    admin = login(client, company.admin)
    r = client.post(f"/users/{company.sales1.id}/deactivate", headers=auth(admin))
    assert r.status_code == 200
    assert client.get("/auth/me", headers=auth(token)).status_code == 401  # same token, now refused


def test_admin_cannot_deactivate_themselves(client, company):
    admin = login(client, company.admin)
    assert client.post(f"/users/{company.admin.id}/deactivate", headers=auth(admin)).status_code == 400


def test_only_admins_manage_users(client, company):
    token = login(client, company.sales1)
    assert client.get("/users", headers=auth(token)).status_code == 403
    r = client.post("/users", headers=auth(token), json={
        "email": "x@example.com", "name": "X", "role": "salesperson", "password": "long-enough-pass"})
    assert r.status_code == 403


def test_admin_creates_user_and_weak_passwords_are_refused(client, company):
    admin = auth(login(client, company.admin))
    ok = client.post("/users", headers=admin, json={
        "email": f"new-{company.tenant_id.hex[:6]}@example.com", "name": "New Person",
        "role": "salesperson", "password": "long-enough-pass"})
    assert ok.status_code == 201 and ok.json()["mfa_enrolled"] is False
    weak = client.post("/users", headers=admin, json={
        "email": "weak@example.com", "name": "Weak", "role": "salesperson", "password": "short"})
    assert weak.status_code == 422
    dup = client.post("/users", headers=admin, json={
        "email": company.sales1.email.upper(), "name": "Dup", "role": "salesperson", "password": "long-enough-pass"})
    assert dup.status_code == 409


def test_admin_cannot_create_an_owner(client, company):
    admin = auth(login(client, company.admin))
    r = client.post("/users", headers=admin, json={
        "email": "boss@example.com", "name": "Boss", "role": "owner", "password": "long-enough-pass"})
    assert r.status_code == 403


def test_change_password(client, company):
    token = auth(login(client, company.sales1))
    bad = client.post("/auth/change-password", headers=token,
                      json={"old_password": "not-my-password", "new_password": "a-brand-new-password"})
    assert bad.status_code == 400
    ok = client.post("/auth/change-password", headers=token,
                     json={"old_password": PASSWORD, "new_password": "a-brand-new-password"})
    assert ok.status_code == 200
    assert client.post("/auth/login", json={"email": company.sales1.email, "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": company.sales1.email, "password": "a-brand-new-password"}).status_code == 200
