"""Translate between the Anthropic-style messages the agent loop uses and the OpenAI chat format
that Ollama, Groq, Gemini and most other providers speak. Pure functions, no network."""
import json
import re
import uuid
from dataclasses import dataclass, field


@dataclass
class Block:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class Response:
    content: list
    stop_reason: str = "end_turn"


def to_openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


def to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        role, content = m["role"], m["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if role == "assistant":
            text = "".join(b["text"] for b in content if b["type"] == "text")
            calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {
                        "name": b["name"],
                        "arguments": json.dumps(b["input"], ensure_ascii=False),
                    },
                }
                for b in content
                if b["type"] == "tool_use"
            ]
            msg = {"role": "assistant", "content": text}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
        else:
            for b in content:
                if b["type"] == "tool_result":
                    body = b["content"] if isinstance(b["content"], str) else json.dumps(b["content"])
                    out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": body})
                elif b["type"] == "text":
                    out.append({"role": "user", "content": b["text"]})
    return out


_THINK = re.compile(r"<think>.*?</think>", re.S)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


def _text_tool_call(text: str, tool_names) -> tuple[str, dict] | None:
    """Some small models write the tool call as JSON text instead of using the tool-call field."""
    body = _FENCE.sub("", text.strip()).strip()
    if not body.startswith("{"):
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("name") not in tool_names:
        return None
    args = data.get("arguments", data.get("parameters", {}))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {}
    return data["name"], args if isinstance(args, dict) else {}


def from_openai_response(data: dict, tool_names=()) -> Response:
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    text = _THINK.sub("", msg.get("content") or "").strip()
    blocks: list[Block] = []

    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except ValueError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        blocks.append(
            Block("tool_use", id=tc.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                  name=fn.get("name", ""), input=args)
        )

    if not blocks and text:
        found = _text_tool_call(text, tool_names)
        if found:
            blocks.append(Block("tool_use", id=f"call_{uuid.uuid4().hex[:12]}", name=found[0], input=found[1]))
            text = ""

    if text and not blocks:
        blocks.append(Block("text", text=text))
    return Response(blocks, "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn")
