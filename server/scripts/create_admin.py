"""Create the first owner account for a company.

    python scripts/create_admin.py --company "Demo Realty" --email you@example.com --name "Your Name"

Asks for the password (not shown). On first login the app walks you through setting up
an authenticator app, because MFA is required for everyone.
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.models import Tenant, User  # noqa: E402
from app.db.session import engine_owner  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--company", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    a = p.parse_args()

    password = getpass.getpass("Password (10+ characters): ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match.")
    try:
        pw_hash = hash_password(password)
    except ValueError as e:
        raise SystemExit(str(e))

    with Session(engine_owner) as s:
        tenant = s.execute(select(Tenant).where(Tenant.name == a.company)).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name=a.company)
            s.add(tenant)
            s.flush()
        email = a.email.strip().lower()
        exists = s.execute(select(User.id).where(User.email.ilike(email))).first()
        if exists:
            raise SystemExit("A user with that email already exists.")
        s.add(User(tenant_id=tenant.id, email=email, name=a.name, role="owner", password_hash=pw_hash))
        s.commit()
    print(f"Created owner {email} for {a.company}. Log in to set up your authenticator app.")


if __name__ == "__main__":
    main()
