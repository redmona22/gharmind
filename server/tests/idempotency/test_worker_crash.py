from datetime import timedelta

from app.core.idempotency import claim, complete
from app.core.tenancy import tenant_session


def test_crashed_worker_is_retried_exactly_once(wa_tenant):
    tid, _ = wa_tenant

    with tenant_session(tid) as s:
        assert claim(s, tid, "k1", "op").status == "claimed"
    # The worker dies here: the key is stuck in "processing".

    with tenant_session(tid) as s:
        assert claim(s, tid, "k1", "op").status == "in_progress"

    # After the timeout, another worker may take over.
    with tenant_session(tid) as s:
        assert claim(s, tid, "k1", "op", stale_after=timedelta(0)).status == "claimed"
    with tenant_session(tid) as s:
        complete(s, tid, "k1", {"ok": True})

    with tenant_session(tid) as s:
        c = claim(s, tid, "k1", "op")
    assert c.status == "done" and c.result == {"ok": True}