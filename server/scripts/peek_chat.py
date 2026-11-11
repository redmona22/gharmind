import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.session import engine_owner  # noqa: E402

PHONE = "+919999900001"
with engine_owner.connect() as c:
    print("contact + conversation:")
    for row in c.execute(text(
        "select c.phone, c.consent_status, c.lead_score, v.status, v.assigned_user_id "
        "from contacts c left join conversations v on v.contact_id = c.id where c.phone = :p"
    ), {"p": PHONE}):
        print("  ", tuple(row))
    print("last messages:")
    for row in c.execute(text(
        "select m.direction, m.sender, left(m.content, 80) from messages m "
        "join conversations v on v.id = m.conversation_id join contacts c on c.id = v.contact_id "
        "where c.phone = :p order by m.created_at desc limit 8"
    ), {"p": PHONE}):
        print("  ", tuple(row))
    print("last audit entries:")
    for row in c.execute(text(
        "select action, left(detail::text, 160) from audit_log order by created_at desc limit 8"
    )):
        print("  ", tuple(row))