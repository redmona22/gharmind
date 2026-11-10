"""Outbound WhatsApp. Real sender for Meta's Cloud API, plus a console sender for development."""
import logging
import uuid

import httpx

from app.config import settings
from app.utils.phone import digits

log = logging.getLogger(__name__)


class SendError(Exception):
    def __init__(self, message: str, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class CloudApiSender:
    """Sends plain text through WhatsApp Business Cloud API. Returns the message id (wamid)."""

    def __init__(self, token: str, phone_number_id: str, api_version: str = "v21.0",
                 client: httpx.Client | None = None, timeout: float = 10.0):
        self._url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = client
        self._timeout = timeout

    def send_text(self, to: str, text: str) -> str:
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": digits(to),
            "type": "text",
            "text": {"preview_url": False, "body": text[:4000]},
        }
        try:
            if self._client is not None:
                r = self._client.post(self._url, json=body, headers=self._headers)
            else:
                r = httpx.post(self._url, json=body, headers=self._headers, timeout=self._timeout)
        except httpx.TransportError as e:  # timeouts, connection errors
            raise SendError(f"WhatsApp unreachable: {type(e).__name__}", retryable=True)

        if r.status_code >= 500 or r.status_code == 429:
            raise SendError(f"WhatsApp temporary error {r.status_code}", retryable=True)
        if r.status_code >= 400:
            try:
                detail = r.json()["error"]["message"]
            except Exception:
                detail = "no detail"
            raise SendError(f"WhatsApp rejected the message ({r.status_code}): {detail}", retryable=False)
        try:
            return r.json()["messages"][0]["id"]
        except Exception:
            raise SendError("WhatsApp gave an unexpected response", retryable=False)


class ConsoleSender:
    """Development only: prints the reply instead of sending it."""

    def send_text(self, to: str, text: str) -> str:
        print(f"\n[Gharmind -> {to}]\n{text}\n", flush=True)
        return f"console.{uuid.uuid4()}"


def get_sender():
    if settings.whatsapp_access_token and settings.whatsapp_phone_number_id:
        return CloudApiSender(
            settings.whatsapp_access_token,
            settings.whatsapp_phone_number_id,
            settings.whatsapp_api_version,
        )
    if settings.app_env == "production":
        raise RuntimeError("WhatsApp credentials are missing in production")
    log.warning("No WhatsApp credentials: replies are printed, not sent")
    return ConsoleSender()
