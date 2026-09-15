import json

import httpx2
import pytest
from openai import OpenAI

from assistant.errors import LLMError
from assistant.llm import ToolCall, Usage
from assistant.llm_openai import OpenAIResponses, load_api_key

FORMAT = {"name": "qa_answer", "schema": {"type": "object", "additionalProperties": False, "required": ["status"],
                                          "properties": {"status": {"type": "string"}}}}
BASE = {"id": "resp_1", "object": "response", "created_at": 0, "model": "gpt-5.6-sol", "output": [],
        "status": "in_progress", "tools": [], "tool_choice": "auto", "parallel_tool_calls": True}
USAGE = {"input_tokens": 1500, "input_tokens_details": {"cached_tokens": 1024, "cache_write_tokens": 100},
         "output_tokens": 120, "output_tokens_details": {"reasoning_tokens": 80}, "total_tokens": 1620}
REASONING = {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "ENC", "status": "completed"}
SEARCH_CALL = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "search",
               "arguments": '{"query":"한미","years":null,"k":null}', "status": "completed"}
SERVER_FAIL = {"error": {"message": "x", "type": "server_error", "param": None, "code": None}}


def message(text, phase="final_answer"):
    return {"type": "message", "id": f"msg_{phase}", "role": "assistant", "status": "completed", "phase": phase,
            "content": [{"type": "output_text", "text": text, "annotations": []}]}


def stream_events(items, *, status="completed", terminal_output=True, extra=None):
    events = [{"type": "response.created", "response": BASE}]
    for index, item in enumerate(items):
        added = dict(item)
        if item["type"] == "function_call":
            added["arguments"] = ""
        if item["type"] == "message":
            added["content"] = []
        events.append({"type": "response.output_item.added", "output_index": index, "item": added})
        events.append({"type": "response.output_item.done", "output_index": index, "item": item})
    final = {**BASE, "status": status, "output": items if terminal_output else [], "usage": USAGE, **(extra or {})}
    events.append({"type": f"response.{status}", "response": final})
    for number, event in enumerate(events):
        event["sequence_number"] = number
    return events


def sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
                   for e in events).encode("utf-8")


class Server:
    """Scripted HTTP answers for the real SDK client."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(json.loads(request.content or b"{}"))
        status, body = self.responses.pop(0)
        if isinstance(body, list):
            return httpx2.Response(status, headers={"content-type": "text/event-stream"}, content=sse(body))
        return httpx2.Response(status, json=body)


def make_llm(server, sleeps=None):
    client = OpenAI(api_key="test-key-not-real", base_url="https://mock.invalid/v1", max_retries=0,
                    http_client=httpx2.Client(transport=httpx2.MockTransport(server)))
    return OpenAIResponses(client, sleep=sleeps.append if sleeps is not None else (lambda seconds: None))


def ask(llm, seen=None):
    events = seen if seen is not None else []
    return llm.turn(instructions="지시", history=[{"role": "user", "content": "질문"}], tools=[], answer_schema=FORMAT,
                    tool_choice="auto", max_output_tokens=8000, safety_identifier="a" * 64,
                    on_event=lambda kind, **data: events.append(kind))


def test_tool_call_turn_is_parsed_and_the_request_is_stateless():
    server, seen = Server((200, stream_events([REASONING, SEARCH_CALL]))), []
    result = ask(make_llm(server), seen)
    assert result.status == "completed"
    assert result.tool_calls == [ToolCall("call_1", "search", SEARCH_CALL["arguments"])]
    assert result.output_items[0]["encrypted_content"] == "ENC"
    assert "async_" not in result.output_items[1]
    assert result.usage == Usage(input=1500, cached=1024, cache_write=100, output=120, reasoning=80)
    assert result.model == "gpt-5.6-sol"
    assert seen == ["thinking", "tool_requested"]
    sent = server.requests[0]
    assert sent["store"] is False and sent["stream"] is True
    assert sent["model"] == "gpt-5.6-sol" and sent["reasoning"] == {"effort": "low"}
    assert sent["text"] == {"format": {"type": "json_schema", "name": "qa_answer", "strict": True,
                                       "schema": FORMAT["schema"]}}
    assert sent["safety_identifier"] == "a" * 64
    assert (sent["tool_choice"], sent["max_output_tokens"]) == ("auto", 8000)
    assert sent["input"] == [{"role": "user", "content": "질문"}]


def test_answer_text_skips_commentary_messages():
    items = [message("먼저 찾아볼게요.", phase="commentary"), message('{"status":"answered"}')]
    result = ask(make_llm(Server((200, stream_events(items)))))
    assert result.answer_text == '{"status":"answered"}' and result.tool_calls == []


def test_output_is_rebuilt_from_finished_items_when_the_final_event_has_none():
    events = stream_events([message('{"status":"not_found"}')], terminal_output=False)
    assert ask(make_llm(Server((200, events)))).answer_text == '{"status":"not_found"}'


def test_incomplete_and_refusal_are_reported():
    cut = stream_events([REASONING], status="incomplete", extra={"incomplete_details": {"reason": "max_output_tokens"}})
    result = ask(make_llm(Server((200, cut))))
    assert (result.status, result.incomplete_reason) == ("incomplete", "max_output_tokens")
    refusal = {"type": "message", "id": "m", "role": "assistant", "status": "completed", "phase": "final_answer",
               "content": [{"type": "refusal", "refusal": "I can't help with that."}]}
    assert ask(make_llm(Server((200, stream_events([refusal]))))).refusal == "I can't help with that."


def test_spend_limit_is_never_retried():
    body = {"error": {"message": "limit", "type": "insufficient_quota", "param": None,
                      "code": "project_spend_limit_exceeded"}}
    server, sleeps = Server((429, body), (200, stream_events([message("{}")]))), []
    with pytest.raises(LLMError) as caught:
        ask(make_llm(server, sleeps))
    assert caught.value.notice.kind == "budget"
    assert len(server.requests) == 1 and sleeps == []


def test_rate_limit_and_server_errors_are_retried_twice_before_any_output():
    busy = {"error": {"message": "slow down", "type": "requests", "param": None, "code": "rate_limit_exceeded"}}
    server, sleeps, seen = Server((429, busy), (500, SERVER_FAIL), (200, stream_events([message("{}")]))), [], []
    assert ask(make_llm(server, sleeps), seen).status == "completed"
    assert len(server.requests) == 3 and len(sleeps) == 2 and seen.count("retrying") == 2
    failing = Server((500, SERVER_FAIL), (500, SERVER_FAIL), (500, SERVER_FAIL))
    with pytest.raises(LLMError) as caught:
        ask(make_llm(failing, []))
    assert caught.value.notice.kind == "server_error" and len(failing.requests) == 3


def test_stream_errors_after_output_are_not_retried():
    events = [{"type": "response.created", "sequence_number": 0, "response": BASE},
              {"type": "response.output_item.added", "sequence_number": 1, "output_index": 0, "item": REASONING},
              {"type": "error", "sequence_number": 2, "code": "server_error", "message": "boom", "param": None}]
    server = Server((200, events), (200, stream_events([message("{}")])))
    with pytest.raises(LLMError) as caught:
        ask(make_llm(server, []))
    assert caught.value.notice.kind == "stream_broken" and len(server.requests) == 1


def test_stream_error_before_any_output_is_retried():
    events = [{"type": "response.created", "sequence_number": 0, "response": BASE},
              {"type": "error", "sequence_number": 1, "code": "server_error", "message": "boom", "param": None}]
    server, sleeps = Server((200, events), (200, stream_events([message("{}")]))), []
    assert ask(make_llm(server, sleeps)).status == "completed"
    assert len(server.requests) == 2 and len(sleeps) == 1
    safety = [events[0], {**events[1], "code": "cyber_policy"}]
    blocked = Server((200, safety), (200, stream_events([message("{}")])))
    with pytest.raises(LLMError) as caught:
        ask(make_llm(blocked, []))
    assert caught.value.notice.kind == "safety_stop" and len(blocked.requests) == 1


def test_stream_without_a_final_event_is_broken_after_two_retries():
    cut = [{"type": "response.created", "sequence_number": 0, "response": BASE}]
    server = Server((200, cut), (200, cut), (200, cut))
    with pytest.raises(LLMError) as caught:
        ask(make_llm(server, []))
    assert caught.value.notice.kind == "stream_broken" and len(server.requests) == 3


def test_moderation_returns_flagged_categories_and_never_blocks_on_failure():
    body = {"id": "modr_1", "model": "omni-moderation-latest", "results": [{
        "flagged": True, "categories": {"sexual/minors": True, "violence": False},
        "category_scores": {"sexual/minors": 0.9, "violence": 0.1},
        "category_applied_input_types": {"sexual/minors": ["text"], "violence": ["text"]}}]}
    assert make_llm(Server((200, body))).moderate("질문") == ["sexual/minors"]
    assert make_llm(Server((500, SERVER_FAIL))).moderate("질문") == []


def test_api_key_comes_from_the_environment_or_the_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# 주석\nOPENAI_API_KEY= sk-test-from-file \n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-from-env")
    assert load_api_key(env_file) == "sk-test-from-env"
    monkeypatch.delenv("OPENAI_API_KEY")
    assert load_api_key(env_file) == "sk-test-from-file"
    with pytest.raises(RuntimeError):
        load_api_key(tmp_path / "missing.env")
