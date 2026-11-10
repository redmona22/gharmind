import httpx

from app.agent.llm_translate import Response, from_openai_response, to_openai_messages, to_openai_tools
from app.config import settings


class AnthropicLLM:
    """Claude through Anthropic's paid API."""

    def __init__(self):
        import anthropic

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def create(self, *, model, system, messages, tools, max_tokens):
        return self._client.messages.create(
            model=model, system=system, messages=messages, tools=tools, max_tokens=max_tokens
        )


class OpenAICompatLLM:
    """Any server that speaks the OpenAI chat API: Ollama (free, local), Groq, Gemini, etc."""

    def __init__(self, base_url: str, api_key: str = "", client: httpx.Client | None = None,
                 timeout: float = 180.0, temperature: float = 0.3):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._base = base_url
        self._key = api_key
        self._client = client
        self._timeout = timeout  # local models on a laptop CPU can be slow
        self._temperature = temperature

    def create(self, *, model, system, messages, tools, max_tokens) -> Response:
        body = {
            "model": model,
            "messages": to_openai_messages(system, messages),
            "max_tokens": max_tokens,
            "temperature": self._temperature,
        }
        if tools:
            body["tools"] = to_openai_tools(tools)
        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        post = self._client.post if self._client is not None else httpx.post
        try:
            r = post(self._url, json=body, headers=headers, timeout=self._timeout)
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach the AI server at {self._base}. If you use Ollama, is it running?"
            )
        r.raise_for_status()
        return from_openai_response(r.json(), tool_names=[t["name"] for t in tools or []])


def get_llm():
    if settings.llm_provider == "anthropic":
        return AnthropicLLM()
    return OpenAICompatLLM(settings.llm_base_url, settings.llm_api_key)
