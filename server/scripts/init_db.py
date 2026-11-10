import sys
from pathlib import Path

# Let "from app..." work no matter which folder the script is started from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import models  # noqa: E402, F401  (registers tables)
from app.db.base import Base  # noqa: E402
from app.db.session import engine_owner  # noqa: E402

if "--reset" in sys.argv:
    Base.metadata.drop_all(engine_owner)
    print("Dropped all tables (dev reset).")

Base.metadata.create_all(engine_owner)

sql_path = Path(__file__).resolve().parents[1] / "app" / "db" / "rls.sql"
sql = sql_path.read_text(encoding="utf-8")

conn = engine_owner.raw_connection()
try:
    with conn.cursor() as cur:
        cur.execute(sql)  # no params, so % in format() is left alone
    conn.commit()
finally:
    conn.close()

print("Tables created and row-level security applied.")