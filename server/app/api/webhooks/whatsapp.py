import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.core.tenancy import resolve_tenant_by_whatsapp, tenant_session
from app.db.models import RawEvent
from app.utils.phone import to_e164
from app.workers.process_message import enqueue_message

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])


@router.get("")
def verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    """Meta's one-time verification handshake."""
    token = settings.whatsapp_verify_token
    if hub_mode == "subscribe" and token and hmac.compare_digest(hub_verify_token or "", token):
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="verification failed")


def _valid_signature(body: bytes, header: str | None) -> bool:
    secret = settings.whatsapp_app_secret
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


def _ingest(payload: dict) -> None:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            number = value.get("metadata", {}).get("display_phone_number")
            tenant_id = resolve_tenant_by_whatsapp(number or "")
            if tenant_id is None:
                log.warning("WhatsApp event for unknown number, ignored")
                continue

            # 1. Save the raw event first (audit trail, replay).
            with tenant_session(tenant_id) as s:
                s.add(RawEvent(tenant_id=tenant_id, source="whatsapp", payload=value))

            # 2. Queue each message. Dedupe happens in the worker (by wamid).
            names = {
                c.get("wa_id"): c.get("profile", {}).get("name")
                for c in value.get("contacts", [])
            }
            for m in value.get("messages", []):
                enqueue_message(
                    str(tenant_id),
                    {
                        "wamid": m["id"],
                        "from": to_e164(m.get("from")),
                        "type": m.get("type"),
                        "text": (m.get("text") or {}).get("body"),
                        "timestamp": m.get("timestamp"),
                        "name": names.get(m.get("from")),
                    },
                )


@router.post("")
async def receive(request: Request):
    body = await request.body()
    if not _valid_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="invalid signature")
    try:
        payload = json.loads(body)
    except ValueError:
        return {"status": "ignored"}
    await run_in_threadpool(_ingest, payload)
    return {"status": "ok"}