import uuid
from dataclasses import dataclass

import pyotp
from sqlalchemy.orm import Session

from app.core.encryption import encrypt
from app.core.security import hash_password
from app.db.models import Contact, Conversation, Message, User
from app.db.session import engine_owner

PASSWORD = "correct-horse-battery"


@dataclass
class Person:
    id: uuid.UUID
    email: str
    password: str
    secret: str


@dataclass
class Lead:
    contact_id: uuid.UUID
    conversation_id: uuid.UUID


@dataclass
class Company:
    tenant_id: uuid.UUID
    admin: Person
    sales1: Person
    sales2: Person
    lead1: Lead  # assigned to sales1
    lead2: Lead  # assigned to sales2
    lead3: Lead  # unassigned


def make_person(s: Session, tenant_id, role: str, with_mfa: bool = True) -> Person:
    email = f"{role}-{uuid.uuid4().hex[:10]}@example.com"
    secret = pyotp.random_base32()
    u = User(
        tenant_id=tenant_id, email=email, name=f"Test {role}", role=role,
        password_hash=hash_password(PASSWORD), mfa_secret=encrypt(secret) if with_mfa else None,
    )
    s.add(u)
    s.flush()
    return Person(u.id, email, PASSWORD, secret)


def make_lead(s: Session, tenant_id, name: str, score: int, assigned=None, text: str = "hello") -> Lead:
    c = Contact(
        tenant_id=tenant_id, name=name, phone=f"+9199{uuid.uuid4().int % 10**8:08d}",
        lead_score=score, assigned_user_id=assigned,
    )
    s.add(c)
    s.flush()
    conv = Conversation(tenant_id=tenant_id, contact_id=c.id, assigned_user_id=None)
    s.add(conv)
    s.flush()
    s.add(Message(tenant_id=tenant_id, conversation_id=conv.id, direction="in", sender="client",
                  content=text, wamid=f"in-{uuid.uuid4()}"))
    return Lead(c.id, conv.id)


def login(client, person: Person) -> str:
    r = client.post("/auth/login", json={"email": person.email, "password": person.password})
    assert r.status_code == 200, r.text
    r = client.post("/auth/mfa/verify", json={
        "challenge_token": r.json()["challenge_token"], "code": pyotp.TOTP(person.secret).now()})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def ids(response) -> set:
    return {x["id"] for x in response.json()["items"]}
