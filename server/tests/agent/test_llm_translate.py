import json

from app.agent.llm_translate import from_openai_response, to_openai_messages, to_openai_tools

TOOLS = [{
    "name": "search_listings",
    "description": "Search",
    "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}, "required": []},
}]
NAMES = ["search_listings", "calculate_emi"]


def reply(content=None, tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}]}


def test_tools_become_openai_functions():
    out = to_openai_tools(TOOLS)
    assert out == [{"type": "function", "function": {
        "name": "search_listings", "description": "Search", "parameters": TOOLS[0]["input_schema"]}}]


def test_a_full_tool_round_trip_is_translated_in_order():
    messages = [
        {"role": "user", "content": "2BHK in Patia"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "Let me check."},
            {"type": "tool_use", "id": "t1", "name": "search_listings", "input": {"location": "Patia"}},
        ]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": '{"count": 1}'}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Found one."}]},
        {"role": "user", "content": "thanks"},
    ]
    out = to_openai_messages("SYSTEM", messages)
    assert [m["role"] for m in out] == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert out[0]["content"] == "SYSTEM"
    call = out[2]["tool_calls"][0]
    assert call["id"] == "t1" and call["function"]["name"] == "search_listings"
    assert json.loads(call["function"]["arguments"]) == {"location": "Patia"}
    assert out[3] == {"role": "tool", "tool_call_id": "t1", "content": '{"count": 1}'}
    assert out[4]["content"] == "Found one." and "tool_calls" not in out[4]


def test_plain_text_reply():
    r = from_openai_response(reply("Hello! What is your budget?"))
    assert [b.type for b in r.content] == ["text"] and r.content[0].text.startswith("Hello")
    assert r.stop_reason == "end_turn"


def test_native_tool_call_with_json_string_arguments():
    r = from_openai_response(reply(None, [{"id": "c1", "type": "function", "function": {
        "name": "search_listings", "arguments": '{"location": "Patia"}'}}]), NAMES)
    assert r.stop_reason == "tool_use"
    b = r.content[0]
    assert (b.type, b.id, b.name, b.input) == ("tool_use", "c1", "search_listings", {"location": "Patia"})


def test_arguments_may_already_be_a_dict():
    r = from_openai_response(reply("", [{"id": "c1", "function": {
        "name": "search_listings", "arguments": {"location": "Patia"}}}]), NAMES)
    assert r.content[0].input == {"location": "Patia"}


def test_broken_arguments_and_missing_id_are_survivable():
    r = from_openai_response(reply(None, [{"function": {"name": "search_listings", "arguments": "{oops"}}]), NAMES)
    b = r.content[0]
    assert b.type == "tool_use" and b.input == {} and b.id.startswith("call_")


def test_reasoning_blocks_are_removed():
    r = from_openai_response(reply("<think>let me think about it</think>Sure, happy to help."))
    assert r.content[0].text == "Sure, happy to help."


def test_tool_call_written_as_text_is_recovered():
    text = '{"name": "search_listings", "arguments": {"location": "Patia"}}'
    r = from_openai_response(reply(text), NAMES)
    assert r.stop_reason == "tool_use" and r.content[0].name == "search_listings"
    assert r.content[0].input == {"location": "Patia"}

    fenced = "```json\n" + text + "\n```"
    assert from_openai_response(reply(fenced), NAMES).content[0].type == "tool_use"


def test_json_that_is_not_a_known_tool_stays_text():
    r = from_openai_response(reply('{"name": "delete_everything", "arguments": {}}'), NAMES)
    assert r.content[0].type == "text"


def test_empty_reply_gives_no_blocks():
    assert from_openai_response(reply("")).content == []
