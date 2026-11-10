import json

from fastapi.testclient import TestClient

from app.db.session import engine_owner
from app.main import app
from tests.helpers import count, make_payload, post_webhook, sign


def test_valid_handshake_returns_challenge(sync_webhook):
    r = TestClient(app).get(
        "/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "12345"},
    )
    assert r.status_code == 200 and r.text == "12345"


def test_wrong_verify_token_rejected(sync_webhook):
    r = TestClient(app).get(
        "/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "1"},
    )
    assert r.status_code == 403


def test_bad_signature_rejected_and_nothing_stored(wa_tenant, sync_webhook):
    tid, number = wa_tenant
    r = post_webhook(TestClient(app), make_payload(number), secret="wrong-secret")
    assert r.status_code == 403
    with engine_owner.connect() as conn:
        assert count(conn, "raw_events", tid) == 0
        assert count(conn, "messages", tid) == 0


def test_missing_signature_rejected(wa_tenant, sync_webhook):
    _, number = wa_tenant
    body = json.dumps(make_payload(number)).encode()
    r = TestClient(app).post("/webhooks/whatsapp", content=body)
    assert r.status_code == 403


def test_unknown_number_returns_200_and_enqueues_nothing(sync_webhook, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not enqueue for an unknown number")

    monkeypatch.setattr("app.api.webhooks.whatsapp.enqueue_message", boom)
    r = post_webhook(TestClient(app), make_payload("+910000000000"))
    assert r.status_code == 200


def test_signature_helper_is_hmac_sha256():
    assert sign(b"{}", "s").startswith("sha256=")