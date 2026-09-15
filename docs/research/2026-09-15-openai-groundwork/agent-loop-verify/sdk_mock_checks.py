"""No-network checks of openai 3.14.0 behaviour that the loop design relies on.

A fake HTTP transport (httpx2.MockTransport) plays scripted SSE streams / HTTP errors
into the real SDK client. No API key, no network, no cost.
"""
from __future__ import annotations

import json
import sys

import httpx2
import openai
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")
import agent_loop_demo as demo  # copied demo (verify folder)

RESULTS: dict[str, object] = {}


def sse(events: list[dict]) -> bytes:
    out = []
    for e in events:
        out.append(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n")
    return "".join(out).encode("utf-8")


BASE = {"id": "resp_x", "object": "response", "created_at": 0, "model": "gpt-5.6-sol", "output": [],
        "status": "in_progress", "tools": [], "tool_choice": "auto", "parallel_tool_calls": True}
USAGE = {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
         "output_tokens": 10, "output_tokens_details": {"reasoning_tokens": 10}, "total_tokens": 110}


def client_with(handler, max_retries=2):
    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    return OpenAI(api_key="test-not-a-real-key", base_url="https://mock.invalid/v1", http_client=http,
                  max_retries=max_retries)


def stream_client(events: list[dict]):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse(events))
    return client_with(handler), calls


KW = dict(model="gpt-5.6-sol", input="q", stream=True, store=False)

# 1) an `error` SSE event: yielded as an event or raised by the SDK?
c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                      {"type": "error", "code": "server_error", "message": "boom", "param": None, "sequence_number": 1}])
try:
    kinds = [ev.type for ev in c.responses.create(**KW)]
    RESULTS["1_error_event_top_level"] = {"raised": False, "events": kinds}
except Exception as exc:  # noqa: BLE001
    RESULTS["1_error_event_top_level"] = {"raised": type(exc).__name__, "msg": str(exc)}

# 1b) same, but payload shaped {"type":"error","error":{...}} (defensive: SDK raises APIError)
c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                      {"type": "error", "error": {"code": "server_error", "message": "boom"}, "sequence_number": 1}])
try:
    kinds = [ev.type for ev in c.responses.create(**KW)]
    RESULTS["1b_error_event_nested"] = {"raised": False, "events": kinds}
except Exception as exc:  # noqa: BLE001
    RESULTS["1b_error_event_nested"] = {"raised": type(exc).__name__, "msg": str(exc)}

# 1c) demo.stream_one on an `error` event
c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                      {"type": "error", "code": "server_error", "message": "boom", "param": None, "sequence_number": 1}])
try:
    demo.stream_one(c, KW, lambda *a, **k: None)
    RESULTS["1c_demo_stream_one_error_event"] = "no exception"
except Exception as exc:  # noqa: BLE001
    RESULTS["1c_demo_stream_one_error_event"] = f"{type(exc).__name__}: {exc}"

# 2) response.failed with usage null
failed = {**BASE, "status": "failed", "error": {"code": "server_error", "message": "failed"}, "usage": None}
c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                      {"type": "response.failed", "sequence_number": 1, "response": failed}])
resp, stats = demo.stream_one(c, KW, lambda *a, **k: None)
RESULTS["2_failed_usage_null"] = {"status": resp.status, "usage_row": demo.usage_row(resp.usage),
                                  "error": resp.error.to_dict() if resp.error else None}

# 3) response.incomplete with reason content_filter (safeguard-like) -> demo just says stopped:incomplete
inc = {**BASE, "status": "incomplete", "incomplete_details": {"reason": "content_filter"}, "usage": USAGE}
c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                      {"type": "response.incomplete", "sequence_number": 1, "response": inc}])
resp, stats = demo.stream_one(c, KW, lambda *a, **k: None)
RESULTS["3_incomplete_content_filter"] = {"status": resp.status, "reason": resp.incomplete_details.reason}

# 4) stream cut off (no terminal event) -> no usage at all
c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                      {"type": "response.output_item.added", "sequence_number": 1, "output_index": 0,
                       "item": {"type": "message", "id": "m1", "role": "assistant", "status": "in_progress", "content": []}}])
try:
    demo.stream_one(c, KW, lambda *a, **k: None)
    RESULTS["4_truncated_stream"] = "no exception"
except Exception as exc:  # noqa: BLE001
    RESULTS["4_truncated_stream"] = f"{type(exc).__name__}: {exc}"

# 5) get_final_response() on an incomplete stream (responses.stream helper)
inc2 = {**BASE, "status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "usage": USAGE}
c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                      {"type": "response.incomplete", "sequence_number": 1, "response": inc2}])
try:
    with c.responses.stream(model="gpt-5.6-sol", input="q", store=False) as s:
        s.get_final_response()
    RESULTS["5_get_final_response_incomplete"] = "returned"
except Exception as exc:  # noqa: BLE001
    RESULTS["5_get_final_response_incomplete"] = f"{type(exc).__name__}: {exc}"

# 6) HTTP 429 spend limit: how many attempts with default retries, and what .code says
for label, headers in (("no_header", {}), ("x-should-retry_false", {"x-should-retry": "false"})):
    n = {"n": 0}

    def handler(request, n=n, headers=headers):
        n["n"] += 1
        body = {"error": {"message": "Project spend limit reached", "type": "insufficient_quota",
                          "param": None, "code": "project_spend_limit_exceeded"}}
        return httpx2.Response(429, headers={"content-type": "application/json", "retry-after-ms": "1", **headers},
                               json=body)
    c = client_with(handler, max_retries=2)
    try:
        c.responses.create(**KW)
    except openai.RateLimitError as exc:
        RESULTS[f"6_429_spend_{label}"] = {"attempts": n["n"], "exc": type(exc).__name__, "code": exc.code,
                                           "type": exc.type}

# 7) to_dict vs model_dump of streamed items (async_ key)
from openai._models import construct_type  # noqa: E402
from openai.types.responses import ResponseOutputItem  # noqa: E402
fc = construct_type(type_=ResponseOutputItem, value={"type": "function_call", "id": "fc_1", "call_id": "call_1",
                                                     "name": "search", "arguments": "{}", "status": "completed"})
msg = construct_type(type_=ResponseOutputItem, value={"type": "message", "id": "m1", "role": "assistant",
                                                      "status": "completed", "phase": "final_answer",
                                                      "content": [{"type": "output_text", "text": "x", "annotations": []}]})
RESULTS["7_function_call_model_dump_keys"] = sorted(fc.model_dump().keys())
RESULTS["7_function_call_to_dict_keys"] = sorted(fc.to_dict().keys())
RESULTS["7_message_to_dict"] = msg.to_dict()

# 8) unknown future event type does not crash iteration
c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                      {"type": "response.some_future_event", "sequence_number": 1, "foo": 1},
                      {"type": "response.completed", "sequence_number": 2, "response": {**BASE, "status": "completed", "usage": USAGE}}])
try:
    resp, stats = demo.stream_one(c, KW, lambda *a, **k: None)
    RESULTS["8_unknown_event"] = {"ok": True, "order": stats["event_order"]}
except Exception as exc:  # noqa: BLE001
    RESULTS["8_unknown_event"] = f"{type(exc).__name__}: {exc}"

# 9) terminal response with output=None vs [] -> recovery from output_item.done
item = {"type": "message", "id": "m1", "role": "assistant", "status": "completed", "phase": "final_answer",
        "content": [{"type": "output_text", "text": "hi", "annotations": []}]}
for label, out in (("output_null", None), ("output_empty", [])):
    term = {**BASE, "status": "completed", "usage": USAGE}
    term["output"] = out
    c, _ = stream_client([{"type": "response.created", "sequence_number": 0, "response": BASE},
                          {"type": "response.output_item.added", "sequence_number": 1, "output_index": 0, "item": {**item, "content": []}},
                          {"type": "response.output_item.done", "sequence_number": 2, "output_index": 0, "item": item},
                          {"type": "response.completed", "sequence_number": 3, "response": term}])
    try:
        resp, stats = demo.stream_one(c, KW, lambda *a, **k: None)
        RESULTS[f"9_{label}"] = {"output_text": resp.output_text, "recovered": stats["output_recovered_from_item_done"]}
    except Exception as exc:  # noqa: BLE001
        RESULTS[f"9_{label}"] = f"{type(exc).__name__}: {exc}"

print(json.dumps(RESULTS, ensure_ascii=False, indent=1, default=str))
