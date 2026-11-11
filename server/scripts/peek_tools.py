import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.session import engine_owner  # noqa: E402

with engine_owner.connect() as c:
    for row in c.execute(text(
        "select action, left(detail::text, 260) from audit_log "
        "where action like 'tool:%' or action = 'reply_checked' order by created_at desc limit 8"
    )):
        print(tuple(row))