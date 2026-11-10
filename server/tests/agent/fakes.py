import uuid
from dataclasses import dataclass, field

from app.integrations.whatsapp import SendError


@dataclass
class Block:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class Resp:
    content: list
    stop_reason: str = "end_turn"


def say(text: str) -> Resp:
    return Resp([Block("text", text=text)])


def call(name: str, **args) -> Resp:
    return Resp([Block("tool_use", id=f"tu_{name}", name=name, input=args)], "tool_use")


class ScriptedLLM:
    """Plays back canned responses in order; repeats the last one when it runs out."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


class BrokenLLM:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        raise RuntimeError("AI provider is down")


class RecordingSender:
    """Stands in for WhatsApp: remembers what would have been sent."""

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_text(self, to, text):
        self.sent.append((to, text))
        return f"out.{uuid.uuid4()}"


class FailingSender:
    def __init__(self, retryable: bool):
        self.retryable = retryable
        self.attempts = 0

    def send_text(self, to, text):
        self.attempts += 1
        raise SendError("simulated WhatsApp failure", retryable=self.retryable)
