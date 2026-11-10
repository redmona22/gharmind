import json

import httpx
import pytest

from app.agent.llm_client import OpenAICompatLLM

TOOLS = [{"name": "search_listings", "description": "Search",
          "input_schema": {"type": "object", "properties": {}, "required": []}}]


def make(handler, key=""):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatLLM("http://localhost:11434/v1/", key, client=client)


def call(llm, tools=TOOLS):
    return llm.create(model="qwen2.5:7b", system="SYS",
                      messages=[{"role": "user", "content": "hi"}], tools=tools, max_tokens=300)


def test_request_shape_and_text_reply():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Hello!"}}]})

    r = call(make(handler))
    assert r.content[0].text == "Hello!"
    assert seen["url"] == "http://localhost:11434/v1/chat/completions"
    assert seen["auth"] is None  # Ollama needs no key
    body = seen["body"]
    assert body["model"] == "qwen2.5:7b" and body["max_tokens"] == 300
    assert body["messages"][0] == {"role": "system", "content": "SYS"}
    assert body["tools"][0]["function"]["name"] == "search_listings"


def test_api_key_is_sent_when_configured():
    seen = {}

    def handler(req):
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    call(make(handler, key="secret"))
    assert seen["auth"] == "Bearer secret"


def test_tool_call_comes_back_as_a_tool_use_block():
    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "function": {"name": "search_listings", "arguments": "{}"}}]}}]})

    r = call(make(handler))
    assert r.stop_reason == "tool_use" and r.content[0].name == "search_listings"


def test_server_error_raises():
    with pytest.raises(httpx.HTTPStatusError):
        call(make(lambda req: httpx.Response(500)))


def test_unreachable_server_gives_a_helpful_message():
    def handler(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(RuntimeError, match="is it running"):
        call(make(handler))
