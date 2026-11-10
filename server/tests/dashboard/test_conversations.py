import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Handoff
from app.db.session import engine_owner
from tests.agent.fakes import FailingSender, RecordingSender
from tests.dashboard.helpers import auth, login


def scalar(sql, **p):
    with engine_owner.connect() as conn:
        return conn.execute(text(sql), p).scalar()


@pytest.fixture()
def sender(monkeypatch):
    s = RecordingSender()
    monkeypatch.setattr("app.api.routes.conversations.get_sender", lambda: s)
    return s


def msg_url(lead):
    return f"/conversations/{lead.conversation_id}/messages"


def test_messages_are_listed_in_order(client, company):
    token = auth(login(client, company.sales1))
    r = client.get(msg_url(company.lead1), headers=token)
    assert r.status_code == 200
    assert [m["content"] for m in r.json()["items"]] == ["hello from one"]
    assert r.json()["status"] == "agent"


def test_salesperson_cannot_read_or_control_someone_elses_conversation(client, company):
    token = auth(login(client, company.sales1))
    assert client.get(msg_url(company.lead2), headers=token).status_code == 404
    assert client.post(f"/conversations/{company.lead2.conversation_id}/takeover", headers=token).status_code == 404
    assert client.post(f"/conversations/{company.lead2.conversation_id}/release", headers=token).status_code == 404
    r = client.post(msg_url(company.lead2), headers=token, json={"text": "hi", "client_message_id": "a"})
    assert r.status_code == 404


def test_other_company_conversations_are_invisible_even_to_admins(client, company, other_company):
    admin = auth(login(client, company.admin))
    assert client.get(msg_url(other_company.lead1), headers=admin).status_code == 404


def test_takeover_then_release_resolves_handoffs(client, company):
    with Session(engine_owner) as s:
        s.add(Handoff(tenant_id=company.tenant_id, conversation_id=company.lead1.conversation_id,
                      reason="price_negotiation", summary="wants a discount"))
        s.commit()
    token = auth(login(client, company.sales1))
    cid = company.lead1.conversation_id

    r = client.post(f"/conversations/{cid}/takeover", headers=token)
    assert r.status_code == 200 and r.json()["status"] == "human"
    assert scalar("SELECT status FROM conversations WHERE id = :c", c=cid) == "human"
    assert scalar("SELECT assigned_user_id FROM conversations WHERE id = :c", c=cid) == company.sales1.id

    r = client.post(f"/conversations/{cid}/release", headers=token)
    assert r.status_code == 200 and r.json()["status"] == "agent"
    assert scalar("SELECT status FROM conversations WHERE id = :c", c=cid) == "agent"
    assert scalar("SELECT resolved FROM handoffs WHERE conversation_id = :c", c=cid) is True


def test_must_take_over_before_replying(client, company, sender):
    token = auth(login(client, company.sales1))
    r = client.post(msg_url(company.lead1), headers=token, json={"text": "hi there", "client_message_id": "m1"})
    assert r.status_code == 409
    assert sender.sent == []


def test_human_reply_is_sent_once_even_if_clicked_twice(client, company, sender):
    token = auth(login(client, company.sales1))
    client.post(f"/conversations/{company.lead1.conversation_id}/takeover", headers=token)
    body = {"text": "Hello, this is Ravi from the team.", "client_message_id": "click-1"}
    a = client.post(msg_url(company.lead1), headers=token, json=body)
    b = client.post(msg_url(company.lead1), headers=token, json=body)
    assert a.status_code == 201 and b.status_code == 201
    assert a.json() == b.json()
    assert len(sender.sent) == 1 and sender.sent[0][1] == body["text"]
    n = scalar("SELECT count(*) FROM messages WHERE conversation_id = :c AND sender = 'human'",
               c=company.lead1.conversation_id)
    assert n == 1


def test_a_second_message_with_a_new_id_is_a_new_message(client, company, sender):
    token = auth(login(client, company.sales1))
    client.post(f"/conversations/{company.lead1.conversation_id}/takeover", headers=token)
    client.post(msg_url(company.lead1), headers=token, json={"text": "one", "client_message_id": "a"})
    client.post(msg_url(company.lead1), headers=token, json={"text": "two", "client_message_id": "b"})
    assert [t for _, t in sender.sent] == ["one", "two"]


def test_no_free_form_reply_after_24_hours(client, company, sender):
    with Session(engine_owner) as s:
        s.execute(text("UPDATE messages SET created_at = now() - interval '30 hours' WHERE conversation_id = :c"),
                  {"c": company.lead1.conversation_id})
        s.commit()
    token = auth(login(client, company.sales1))
    client.post(f"/conversations/{company.lead1.conversation_id}/takeover", headers=token)
    r = client.post(msg_url(company.lead1), headers=token, json={"text": "late reply", "client_message_id": "x"})
    assert r.status_code == 409 and "window_expired" in r.text
    assert sender.sent == []


def test_opted_out_customers_cannot_be_messaged(client, company, sender):
    with Session(engine_owner) as s:
        s.execute(text("UPDATE contacts SET consent_status = 'opted_out' WHERE id = :c"),
                  {"c": company.lead1.contact_id})
        s.commit()
    token = auth(login(client, company.sales1))
    client.post(f"/conversations/{company.lead1.conversation_id}/takeover", headers=token)
    r = client.post(msg_url(company.lead1), headers=token, json={"text": "hello?", "client_message_id": "y"})
    assert r.status_code == 403 and sender.sent == []


def test_failed_send_returns_502_and_can_be_retried_once(client, company, monkeypatch):
    token = auth(login(client, company.sales1))
    client.post(f"/conversations/{company.lead1.conversation_id}/takeover", headers=token)
    body = {"text": "Hello again", "client_message_id": "retry-me"}

    monkeypatch.setattr("app.api.routes.conversations.get_sender", lambda: FailingSender(retryable=True))
    assert client.post(msg_url(company.lead1), headers=token, json=body).status_code == 502
    assert scalar("SELECT count(*) FROM messages WHERE conversation_id = :c AND sender = 'human'",
                  c=company.lead1.conversation_id) == 0

    good = RecordingSender()
    monkeypatch.setattr("app.api.routes.conversations.get_sender", lambda: good)
    assert client.post(msg_url(company.lead1), headers=token, json=body).status_code == 201
    assert len(good.sent) == 1


def test_admin_can_take_over_any_conversation_in_their_company(client, company, sender):
    admin = auth(login(client, company.admin))
    cid = company.lead2.conversation_id
    assert client.post(f"/conversations/{cid}/takeover", headers=admin).status_code == 200
    r = client.post(msg_url(company.lead2), headers=admin, json={"text": "Admin here", "client_message_id": "z"})
    assert r.status_code == 201


def test_salesperson_cannot_reply_in_a_conversation_another_person_took_over(client, company, sender):
    admin = auth(login(client, company.admin))
    sales = auth(login(client, company.sales1))
    cid = company.lead1.conversation_id
    client.post(f"/conversations/{cid}/takeover", headers=admin)  # admin now handles it
    r = client.post(msg_url(company.lead1), headers=sales, json={"text": "me too", "client_message_id": "q"})
    assert r.status_code == 403 and sender.sent == []
