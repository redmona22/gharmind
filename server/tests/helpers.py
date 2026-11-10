import hashlib
import hmac
import json


def make_payload(number: str, wamid: str = "wamid.TEST1",
                 sender: str = "919811111111", text: str = "Hi, 2BHK in Bhubaneswar?") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": number.lstrip("+"), "phone_number_id": "123"},
                    "contacts": [{"profile": {"name": "Ravi"}, "wa_id": sender}],
                    "messages": [{
                        "from": sender, "id": wamid, "timestamp": "1760000000",
                        "type": "text", "text": {"body": text},
                    }],
                },
            }],
        }],
    }


def sign(body: bytes, secret: str = "testsecret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post_webhook(client, payload: dict, secret: str = "testsecret"):
    body = json.dumps(payload).encode()
    return client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": sign(body, secret), "Content-Type": "application/json"},
    )


def count(conn, table: str, tenant_id) -> int:
    from sqlalchemy import text
    return conn.execute(
        text(f"SELECT count(*) FROM {table} WHERE tenant_id = :t"), {"t": tenant_id}
    ).scalar()