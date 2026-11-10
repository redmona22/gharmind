import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Contact
from app.db.session import engine_owner
from app.workers.process_message import handle_inbound_message


def _message(phone: str, text: str = "hi") -> dict:
    return {
        "wamid": f"wamid.{uuid.uuid4().hex}", "from": phone, "type": "text",
        "text": text, "timestamp": "1760000000", "name": "Ravi",
    }


def _phone() -> str:
    return f"+9197{uuid.uuid4().int % 10**8:08d}"


def _assigned_to(tid, phone):
    with Session(engine_owner) as s:
        return s.execute(
            select(Contact.assigned_user_id).where(Contact.tenant_id == tid, Contact.phone == phone)
        ).scalar_one()


def test_new_leads_rotate_between_active_salespeople(team_tenant):
    tid, ids = team_tenant
    phones = [_phone() for _ in range(4)]
    for p in phones:
        assert handle_inbound_message(str(tid), _message(p)) == "stored"
    got = [_assigned_to(tid, p) for p in phones]

    assert set(got) == {ids["sales_a"], ids["sales_b"]}  # never the admin or the deactivated one
    assert got.count(ids["sales_a"]) == 2 and got.count(ids["sales_b"]) == 2
    assert got[0] != got[1] and got[1] != got[2] and got[2] != got[3]  # they alternate


def test_a_returning_customer_is_not_reassigned(team_tenant):
    tid, _ = team_tenant
    phone = _phone()
    handle_inbound_message(str(tid), _message(phone))
    first = _assigned_to(tid, phone)
    for _ in range(3):
        handle_inbound_message(str(tid), _message(phone, "still there?"))
    assert _assigned_to(tid, phone) == first


def test_no_salespeople_leaves_the_lead_unassigned(wa_tenant):
    tid, _ = wa_tenant
    phone = _phone()
    assert handle_inbound_message(str(tid), _message(phone)) == "stored"
    assert _assigned_to(tid, phone) is None