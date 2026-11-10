from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Owner connection: schema creation, migrations, test seeding. Bypasses RLS.
engine_owner = create_engine(settings.database_url, pool_pre_ping=True)

# App connection: API and workers. Subject to row-level security.
engine_app = create_engine(settings.database_url_app, pool_pre_ping=True)
SessionApp = sessionmaker(engine_app, expire_on_commit=False)