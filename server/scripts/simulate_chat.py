"""Chat with Gharmind in your terminal, no WhatsApp needed.

    python scripts/simulate_chat.py          # continue the demo conversation
    python scripts/simulate_chat.py --new    # start as a brand-new customer

Uses the real pipeline (store message -> agent -> reply) with the real database.
Needs Docker running and `init_db.py` done. Set ANTHROPIC_API_KEY in .env for real answers;
without it Gharmind answers with the holding message and hands the chat to a human.
"""
import logging
import sys
import uuid
from pathlib import Path

logging.basicConfig(level=logging.WARNING)  # so problems with the AI server are visible

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.workers.process_message as pm  # noqa: E402
from app.config import settings  # noqa: E402
from app.db.models import Listing, Tenant  # noqa: E402
from app.db.session import engine_owner  # noqa: E402
from app.integrations.whatsapp import ConsoleSender  # noqa: E402
from app.workers.process_message import handle_inbound_message  # noqa: E402
from app.workers.reply import handle_reply  # noqa: E402

DEMO_NUMBER = "+910000000001"
DEMO_CUSTOMER = "+919999900001"

# DEMO data only. The RERA numbers are made up.
DEMO_LISTINGS = [
    dict(listing_type="sale", project="Sunrise Heights (demo)", price=4_500_000, bhk=2, area_sqft=1050,
         location="Patia, Bhubaneswar", rera_number="DEMO/RERA/001"),
    dict(listing_type="sale", project="Lake View Residency (demo)", price=6_200_000, bhk=3, area_sqft=1450,
         location="Chandrasekharpur, Bhubaneswar", rera_number="DEMO/RERA/002"),
    dict(listing_type="sale", project="Green Park Villas (demo)", price=8_900_000, bhk=3, area_sqft=1800,
         location="Khandagiri, Bhubaneswar", rera_number="DEMO/RERA/003"),
    dict(listing_type="rent", project="Green Nest (demo)", price=18_000, deposit=90_000, bhk=2, area_sqft=1000,
         location="Patia, Bhubaneswar", furnishing="semi-furnished"),
]


def ensure_demo_tenant() -> uuid.UUID:
    with Session(engine_owner) as s:
        tenant = s.execute(select(Tenant).where(Tenant.whatsapp_number == DEMO_NUMBER)).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="Demo Realty", whatsapp_number=DEMO_NUMBER)
            s.add(tenant)
            s.flush()
        has_listings = s.execute(select(Listing.id).where(Listing.tenant_id == tenant.id).limit(1)).first()
        if not has_listings:
            for row in DEMO_LISTINGS:
                s.add(Listing(tenant_id=tenant.id, **row))
        s.commit()
        return tenant.id


def check_ai_server() -> None:
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            print("NOTE: ANTHROPIC_API_KEY is not set, so Gharmind will hand every chat to a human.\n")
        return
    import httpx

    url = settings.llm_base_url.rstrip("/") + "/models"
    try:
        httpx.get(url, timeout=3.0)
        print(f"AI server reachable at {settings.llm_base_url} (model: {settings.llm_model_routine})\n")
    except Exception:
        print(
            f"NOTE: cannot reach the AI server at {settings.llm_base_url}.\n"
            f"If you use Ollama: start it, then run  ollama pull {settings.llm_model_routine}\n"
            "Until then Gharmind will hand every chat to a human.\n"
        )


def main() -> None:
    tid = ensure_demo_tenant()
    customer = f"+9199{uuid.uuid4().int % 10**8:08d}" if "--new" in sys.argv else DEMO_CUSTOMER

    queued: list[tuple] = []
    pm.enqueue_reply = lambda t, c, w: queued.append((t, c, w))  # run the reply inline instead
    sender = ConsoleSender()

    check_ai_server()
    print(f"Chatting as {customer} with Demo Realty. Type a message, or 'quit'.\n")

    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text.lower() in ("quit", "exit"):
            break
        wamid = f"sim.{uuid.uuid4()}"
        handle_inbound_message(
            str(tid),
            {"wamid": wamid, "from": customer, "type": "text", "text": text,
             "timestamp": "0", "name": "Demo Customer"},
        )
        if not queued:
            print("[message was not queued, try again]\n")
            continue
        t, c, w = queued.pop()
        status = handle_reply(t, c, w, sender=sender)
        if status != "sent":
            print(f"[no reply sent: {status}]\n")


if __name__ == "__main__":
    main()
