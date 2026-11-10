import json
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class Claim:
    status: str  # "claimed" (you do the work) | "done" (already finished) | "in_progress" (someone else is on it)
    result: dict | None = None


def claim(
    session: Session,
    tenant_id: uuid.UUID,
    key: str,
    operation: str,
    stale_after: timedelta = timedelta(minutes=5),
) -> Claim:
    """Try to claim an operation. Call inside tenant_session and commit before doing the work.

    The unique constraint on (tenant_id, key) is the real guard, so two workers
    racing for the same key cannot both claim it.
    """
    params = {"id": uuid.uuid4(), "t": tenant_id, "k": key, "op": operation}

    inserted = session.execute(
        text(
            """
            INSERT INTO idempotency_keys (id, tenant_id, key, operation, status)
            VALUES (:id, :t, :k, :op, 'processing')
            ON CONFLICT (tenant_id, key) DO NOTHING
            RETURNING id
            """
        ),
        params,
    ).first()
    if inserted:
        return Claim("claimed")

    row = session.execute(
        text("SELECT status, result FROM idempotency_keys WHERE tenant_id = :t AND key = :k"),
        {"t": tenant_id, "k": key},
    ).first()
    if row is None:  # deleted by cleanup between the two statements; try again
        return claim(session, tenant_id, key, operation, stale_after)
    if row.status == "done":
        return Claim("done", row.result)

    # 'failed', or 'processing' for too long (worker probably died): take over atomically.
    taken = session.execute(
        text(
            """
            UPDATE idempotency_keys
            SET status = 'processing', updated_at = now()
            WHERE tenant_id = :t AND key = :k
              AND (status = 'failed'
                   OR (status = 'processing'
                       AND updated_at < now() - make_interval(secs => :secs)))
            RETURNING id
            """
        ),
        {"t": tenant_id, "k": key, "secs": stale_after.total_seconds()},
    ).first()
    return Claim("claimed") if taken else Claim("in_progress")


def complete(session: Session, tenant_id: uuid.UUID, key: str, result: dict | None = None) -> None:
    """Mark done. Call in the same transaction as the side effect where possible."""
    session.execute(
        text(
            """
            UPDATE idempotency_keys
            SET status = 'done', result = CAST(:r AS jsonb), updated_at = now()
            WHERE tenant_id = :t AND key = :k
            """
        ),
        {"t": tenant_id, "k": key, "r": json.dumps(result or {})},
    )


def fail(session: Session, tenant_id: uuid.UUID, key: str) -> None:
    session.execute(
        text(
            """
            UPDATE idempotency_keys SET status = 'failed', updated_at = now()
            WHERE tenant_id = :t AND key = :k
            """
        ),
        {"t": tenant_id, "k": key},
    )