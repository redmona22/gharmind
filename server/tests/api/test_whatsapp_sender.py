import json

import httpx
import pytest

from app.config import settings
from app.integrations.whatsapp import CloudApiSender, ConsoleSender, SendError, get_sender


def make(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return CloudApiSender("tok", "123456", "v21.0", client=client)


def test_builds_the_right_request_and_returns_the_message_id():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.OUT1"}]})

    assert make(handler).send_text("+919811111111", "Hello") == "wamid.OUT1"
    assert seen["url"] == "https://graph.facebook.com/v21.0/123456/messages"
    assert seen["auth"] == "Bearer tok"
    assert seen["body"]["to"] == "919811111111"  # digits only, no plus
    assert seen["body"]["messaging_product"] == "whatsapp"
    assert seen["body"]["text"]["body"] == "Hello"


@pytest.mark.parametrize("status", [500, 502, 503, 429])
def test_temporary_errors_are_retryable(status):
    with pytest.raises(SendError) as e:
        make(lambda req: httpx.Response(status)).send_text("+919811111111", "Hi")
    assert e.value.retryable is True


def test_rejected_message_is_not_retryable():
    handler = lambda req: httpx.Response(400, json={"error": {"message": "Recipient not in allowed list"}})
    with pytest.raises(SendError) as e:
        make(handler).send_text("+919811111111", "Hi")
    assert e.value.retryable is False and "allowed list" in str(e.value)


def test_network_timeout_is_retryable():
    def handler(req):
        raise httpx.ConnectTimeout("slow")

    with pytest.raises(SendError) as e:
        make(handler).send_text("+919811111111", "Hi")
    assert e.value.retryable is True


def test_unexpected_success_body_is_not_retryable():
    with pytest.raises(SendError) as e:
        make(lambda req: httpx.Response(200, json={"oops": 1})).send_text("+919811111111", "Hi")
    assert e.value.retryable is False


def test_the_token_never_appears_in_errors():
    with pytest.raises(SendError) as e:
        make(lambda req: httpx.Response(401, json={"error": {"message": "bad token"}})).send_text("+91981", "Hi")
    assert "tok" not in str(e.value).replace("token", "")


def test_sender_choice(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_access_token", "")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "")
    monkeypatch.setattr(settings, "app_env", "development")
    assert isinstance(get_sender(), ConsoleSender)

    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(RuntimeError):
        get_sender()

    monkeypatch.setattr(settings, "whatsapp_access_token", "abc")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "999")
    assert isinstance(get_sender(), CloudApiSender)
