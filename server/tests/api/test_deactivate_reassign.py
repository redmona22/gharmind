import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import make_token
from app.db.models import Contact, Conversation, User
from app.db.session import engine_owner
from app.main import app


def _admin_headers(tid, ids):
    token = make_token("access", ids["admin"], tid, 60, role="admin")
    return {"Authorization": f"Bearer {token}"}


def _lead(tid, owner, human_chat=False):
    """A contact assigned to `owner`, optionally with a chat that owner has taken over."""
    with Session(engine_owner) as s:
        c = Contact(tenant_id=tid, phone=f"+9196{uuid.uuid4().int % 10**8:08d}", assigned_user_id=owner)
        s.add(c)
        s.flush()
        conv_id = None
        if human_chat:
            conv = Conversation(tenant_id=tid, contact_id=c.id, channel="whatsapp",
                                status="human", assigned_user_id=owner)
            s.add(conv)
            s.flush()
            conv_id = conv.id
        s.commit()
        return c.id, conv_id


def _owner_of(contact_id):
    with Session(engine_owner) as s:
        return s.execute(select(Contact.assigned_user_id).where(Contact.id == contact_id)).scalar_one()


def _chat_owner(conv_id):
    with Session(engine_owner) as s:
        return s.execute(select(Conversation.assigned_user_id).where(Conversation.id == conv_id)).scalar_one()


def test_leads_and_chats_move_to_the_remaining_salesperson(team_tenant):
    tid, ids = team_tenant
    leads = [_lead(tid, ids["sales_a"], human_chat=(i == 0)) for i in range(3)]

    r = TestClient(app).post(f"/users/{ids['sales_a']}/deactivate", headers=_admin_headers(tid, ids))

    assert r.status_code == 200
    assert r.json()["active"] is False and r.json()["leads_reassigned"] == 3
    # sales_b is the only active salesperson (sales_off is deactivated, admin is not one).
    assert all(_owner_of(c) == ids["sales_b"] for c, _ in leads)
    assert _chat_owner(leads[0][1]) == ids["sales_b"]


def test_leads_become_unassigned_when_nobody_is_left(team_tenant):
    tid, ids = team_tenant
    with Session(engine_owner) as s:
        s.execute(update(User).where(User.id == ids["sales_b"]).values(active=False))
        s.commit()
    contact_id, conv_id = _lead(tid, ids["sales_a"], human_chat=True)

    r = TestClient(app).post(f"/users/{ids['sales_a']}/deactivate", headers=_admin_headers(tid, ids))

    assert r.status_code == 200 and r.json()["leads_reassigned"] == 1
    assert _owner_of(contact_id) is None
    assert _chat_owner(conv_id) is None


def test_other_peoples_leads_are_left_alone(team_tenant):
    tid, ids = team_tenant
    mine, _ = _lead(tid, ids["sales_b"])
    theirs, _ = _lead(tid, ids["sales_a"])

    TestClient(app).post(f"/users/{ids['sales_a']}/deactivate", headers=_admin_headers(tid, ids))

    assert _owner_of(mine) == ids["sales_b"]
    assert _owner_of(theirs) == ids["sales_b"]