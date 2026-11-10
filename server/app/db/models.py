import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.base import Base, TimestampMixin


def _uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TenantMixin:
    @declared_attr
    def tenant_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
        )


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    whatsapp_number: Mapped[str | None] = mapped_column(String(32), unique=True)
    plan: Mapped[str] = mapped_column(String(50), default="pilot")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)


class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="salesperson")  # salesperson | admin | owner
    password_hash: Mapped[str | None] = mapped_column(String(255))
    mfa_secret: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Contact(Base, TimestampMixin, TenantMixin):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("tenant_id", "phone"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")  # en | hi | or
    source: Mapped[str | None] = mapped_column(String(50))
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    qualification: Mapped[dict] = mapped_column(JSONB, default=dict)
    consent_status: Mapped[str] = mapped_column(String(20), default="unknown")  # unknown | opted_in | opted_out
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )


class Consent(Base, TimestampMixin, TenantMixin):
    __tablename__ = "consents"
    id: Mapped[uuid.UUID] = _uuid_pk()
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # opt_in | opt_out
    wording: Mapped[str] = mapped_column(Text, nullable=False)


class Listing(Base, TimestampMixin, TenantMixin):
    __tablename__ = "listings"
    id: Mapped[uuid.UUID] = _uuid_pk()
    listing_type: Mapped[str] = mapped_column(String(10), nullable=False)  # sale | rent
    project: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[int | None] = mapped_column(Integer)  # sale price or monthly rent
    deposit: Mapped[int | None] = mapped_column(Integer)
    bhk: Mapped[int | None] = mapped_column(Integer)
    area_sqft: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(200))
    furnishing: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="available")
    rera_number: Mapped[str | None] = mapped_column(String(100))
    media: Mapped[list] = mapped_column(JSONB, default=list)


class Conversation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30), default="whatsapp")
    status: Mapped[str] = mapped_column(String(20), default="agent")  # agent | human | closed
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Message(Base, TimestampMixin, TenantMixin):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("tenant_id", "wamid"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # in | out
    sender: Mapped[str] = mapped_column(String(10), nullable=False)  # client | agent | human
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_used: Mapped[str | None] = mapped_column(String(100))
    wamid: Mapped[str | None] = mapped_column(String(200))


class Handoff(Base, TimestampMixin, TenantMixin):
    __tablename__ = "handoffs"
    # At most one OPEN handoff per conversation and reason: the real idempotency guard.
    __table_args__ = (
        Index(
            "uq_open_handoff",
            "tenant_id", "conversation_id", "reason",
            unique=True,
            postgresql_where=text("resolved = false"),
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class IdempotencyKey(Base, TimestampMixin, TenantMixin):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "key"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(300), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing | done | failed
    result: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditLog(Base, TimestampMixin, TenantMixin):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = _uuid_pk()
    actor: Mapped[str] = mapped_column(String(100), nullable=False)  # user id, "agent", "system"
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)


class RawEvent(Base, TimestampMixin, TenantMixin):
    __tablename__ = "raw_events"
    id: Mapped[uuid.UUID] = _uuid_pk()
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

class ListingMedia(Base, TimestampMixin, TenantMixin):
    __tablename__ = "listing_media"
    id: Mapped[uuid.UUID] = _uuid_pk()
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)  # as uploaded, for display only
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)  # judged from the file's bytes
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)  # where the file lives
    position: Mapped[int] = mapped_column(Integer, default=0)