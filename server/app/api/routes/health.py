from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine_app

router = APIRouter()


@router.get("/health")
def health():
    with engine_app.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}