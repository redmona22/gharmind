import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.db.session import engine_owner
from app.main import app
from app.workers.process_message import handle_inbound_message
from tests.helpers import count, make_payload, post_webhook


def test_same_webhook_five_times_stores_one_message(wa_tenant, sync_webhook):
    tid, number = wa_tenant
    client = TestClient(app)
    payload = make_payload(number)
    for _ in range(5):
        assert post_webhook(client, payload).status_code == 200
    with engine_owner.connect() as conn:
        assert count(conn, "messages", tid) == 1
        assert count(conn, "contacts", tid) == 1
        assert count(conn, "conversations", tid) == 1
        assert count(conn, "raw_events", tid) == 5  # every delivery is kept for audit


def test_five_workers_racing_on_one_message_store_it_once(wa_tenant):
    tid, number = wa_tenant
    msg = {"wamid": "wamid.RACE", "from": "+919811111111", "type": "text",
           "text": "hello", "timestamp": "1", "name": "Ravi"}
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: handle_inbound_message(str(tid), msg), range(5)))
    assert results.count("stored") == 1
    with engine_owner.connect() as conn:
        assert count(conn, "messages", tid) == 1