import uuid

from pydantic import BaseModel


class AssignIn(BaseModel):
    user_id: uuid.UUID | None = None  # null = unassign
