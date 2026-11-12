import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.session import engine_owner  # noqa: E402

PHONE = "+919999900001"  # the simulator's test number only
with engine_owner.begin() as c:
    n = c.execute(text(
        "update conversations set status = 'agent', assigned_user_id = null "
        "where contact_id in (select id from contacts where phone = :p)"
    ), {"p": PHONE}).rowcount
    h = c.execute(text(
        "update handoffs set resolved = true where resolved = false and conversation_id in "
        "(select v.id from conversations v join contacts k on k.id = v.contact_id where k.phone = :p)"
    ), {"p": PHONE}).rowcount
    c.execute(text("update contacts set consent_status = 'unknown' where phone = :p"), {"p": PHONE})
print(f"reset {PHONE}: {n} conversation(s) back to the agent, {h} handoff(s) closed")