import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import ADMINS, CurrentUser, get_db, require_roles
from app.core.assignment import reassign_leads_from
from app.core.audit import audit
from app.core.security import hash_password
from app.db.models import User
from app.schemas.auth import UserCreateIn

router = APIRouter(tags=["users"])


def _out(u: User) -> dict:
    return {"id": str(u.id), "email": u.email, "name": u.name, "role": u.role,
            "active": u.active, "mfa_enrolled": u.mfa_secret is not None}


def _find(s, user: CurrentUser, user_id: uuid.UUID) -> User:
    u = s.execute(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)).scalar_one_or_none()
    if u is None:
        raise HTTPException(404, "not found")
    if u.role == "owner" and user.role != "owner":
        raise HTTPException(403, "only an owner can change an owner")
    return u


@router.get("")
def list_users(user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db)):
    rows = s.execute(select(User).where(User.tenant_id == user.tenant_id).order_by(User.name)).scalars().all()
    return {"items": [_out(u) for u in rows]}


@router.post("", status_code=201)
def create_user(body: UserCreateIn, user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db)):
    if body.role == "owner" and user.role != "owner":
        raise HTTPException(403, "only an owner can create another owner")
    try:
        pw_hash = hash_password(body.password)
    except ValueError as e:
        raise HTTPException(422, str(e))
    u = User(tenant_id=user.tenant_id, email=body.email, name=body.name, role=body.role, password_hash=pw_hash)
    s.add(u)
    try:
        s.flush()
    except IntegrityError:
        raise HTTPException(409, "a user with this email already exists")
    audit(s, user.tenant_id, str(user.id), "user_created", {"user_id": str(u.id), "role": body.role})
    return _out(u)


@router.post("/{user_id}/deactivate")
def deactivate_user(user_id: uuid.UUID, user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db)):
    """Instant offboarding: their token stops working on the very next request, and their
    leads move to the remaining salespeople."""
    if user_id == user.id:
        raise HTTPException(400, "you cannot deactivate yourself")
    u = _find(s, user, user_id)
    u.active = False
    s.flush()  # the reassignment must see them as inactive
    moved = reassign_leads_from(s, user.tenant_id, u.id)
    audit(s, user.tenant_id, str(user.id), "user_deactivated",
          {"user_id": str(u.id), "leads_reassigned": moved})
    return {**_out(u), "leads_reassigned": moved}


@router.post("/{user_id}/reactivate")
def reactivate_user(user_id: uuid.UUID, user: CurrentUser = Depends(require_roles(*ADMINS)), s=Depends(get_db)):
    """Let a deactivated person log in again with their old password and authenticator.
    Leads that were moved away stay where they are; they just receive new leads again."""
    u = _find(s, user, user_id)
    if not u.active:
        u.active = True
        audit(s, user.tenant_id, str(user.id), "user_reactivated", {"user_id": str(u.id)})
    return _out(u)