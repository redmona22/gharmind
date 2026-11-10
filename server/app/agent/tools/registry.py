import logging
import uuid
from dataclasses import dataclass

from app.core.tenancy import tenant_session
from app.db.models import AuditLog
from app.utils.finance import ToolError  # noqa: F401  (re-exported for tool modules)

log = logging.getLogger(__name__)

_HANDLERS: dict = {}
_SCHEMAS: list[dict] = []


@dataclass
class ToolContext:
    """Set by code from the verified conversation. The model can never change these."""
    tenant_id: uuid.UUID
    contact_id: uuid.UUID
    conversation_id: uuid.UUID


def tool(name: str, description: str, properties: dict, required: list[str] | None = None):
    def register(fn):
        _HANDLERS[name] = fn
        _SCHEMAS.append(
            {
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required or [],
                },
            }
        )
        return fn

    return register


def schemas() -> list[dict]:
    return list(_SCHEMAS)


def execute_tool(name: str, args: dict, ctx: ToolContext) -> dict:
    """Run one tool inside a tenant-locked transaction and write the audit entry with it."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name}"}
    args = args if isinstance(args, dict) else {}
    try:
        with tenant_session(ctx.tenant_id) as s:
            result = handler(s, ctx, args)
            s.add(
                AuditLog(
                    tenant_id=ctx.tenant_id,
                    actor="agent",
                    action=f"tool:{name}",
                    detail={"args": args, "result": result},
                )
            )
        return result
    except ToolError as e:
        return {"error": str(e)}
    except Exception:
        log.exception("tool %s failed", name)
        return {"error": "tool failed, tell the customer the team will follow up"}
