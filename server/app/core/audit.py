import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def audit(session: Session, tenant_id: uuid.UUID, actor: str, action: str, detail: dict | None = None) -> None:
    session.add(AuditLog(tenant_id=tenant_id, actor=actor, action=action, detail=detail or {}))
