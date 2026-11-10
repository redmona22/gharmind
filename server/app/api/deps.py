import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import read_token
from app.core.tenancy import tenant_session
from app.db.models import Contact, User

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    name: str
    email: str


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> CurrentUser:
    """Who is calling. Checked against the database on EVERY request, so switching a
    salesperson off takes effect immediately, not when their token expires."""
    if creds is None:
        raise HTTPException(401, "not authenticated")
    payload = read_token(creds.credentials, "access")
    if payload is None:
        raise HTTPException(401, "invalid or expired token")
    try:
        uid, tid = uuid.UUID(payload["sub"]), uuid.UUID(payload["tid"])
    except (KeyError, ValueError):
        raise HTTPException(401, "invalid token")
    with tenant_session(tid) as s:
        u = s.execute(select(User).where(User.id == uid, User.tenant_id == tid)).scalar_one_or_none()
        if u is None or not u.active:
            raise HTTPException(401, "account disabled")
        return CurrentUser(u.id, u.tenant_id, u.role, u.name, u.email)


def require_roles(*roles: str):
    def check(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(403, "you do not have permission to do this")
        return user

    return check


ADMINS = ("admin", "owner")


def get_db(user: CurrentUser = Depends(current_user)):
    """A database session locked to the caller's company."""
    with tenant_session(user.tenant_id) as s:
        yield s


def visible_contact(s: Session, user: CurrentUser, contact_id: uuid.UUID) -> Contact:
    """A lead the caller may see: salespeople only their own, admins everything in their company.
    Anything else is a 404, so nobody can probe for leads that exist but are not theirs."""
    stmt = select(Contact).where(Contact.id == contact_id, Contact.tenant_id == user.tenant_id)
    if user.role == "salesperson":
        stmt = stmt.where(Contact.assigned_user_id == user.id)
    contact = s.execute(stmt).scalar_one_or_none()
    if contact is None:
        raise HTTPException(404, "not found")
    return contact
