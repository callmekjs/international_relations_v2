"""Verifier re-run: what goes on the wire, with a local MockTransport and a dummy key. No network.

Checks: (1) the current adapter with tools=[] ; (2) create() with tools/tool_choice omitted and flex +
explicit cache mode ; (3) how the adapter's `shown` flag reacts to response.queued and a reasoning item
(does a timeout after 'thinking' still allow a retry?) ; (4) a flex 429 with a long Retry-After ;
(5) a 503 server_is_overloaded."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx2
import openai
from openai import OpenAI

sys.path.insert(0, "C:/international_relations")
from assistant.errors import LLMError, notice_for_exception, retry_delay_s  # noqa: E402
from assistant.llm_openai import OpenAIResponses  # noqa: E402

HERE = Path(__file__).resolve().parent
seen: list[dict] = []
MODE = {"kind": "ok"}


def sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def response(status, output, usage=None, tier="flex"):
    return {"id": "resp_x", "object": "response", "created_at": 0, "model": "gpt-5.6-sol", "status": status,
            "service_tier": tier, "tools": [], "tool_choice": "auto", "parallel_tool_calls": True, "output": output,
            "usage": usage}


def handler(request: httpx2.Request) -> httpx2.Response:
    body = json.loads(request.content)
    seen.append({"keys": sorted(body), "tools": body.get("tools", "<absent>"), "tool_choice": body.get("tool_choice", "<absent>"),
                 "service_tier": body.get("service_tier", "<absent>"), "timeout_header": request.headers.get("x-stainless-timeout")})
    kind = MODE["kind"]
    if kind == "429_long_retry_after":
        return httpx2.Response(429, headers={"retry-after": "60"},
                               json={"error": {"message": "Resource Unavailable", "type": "rate_limit_error", "code": None, "param": None}})
    if kind == "503":
        return httpx2.Response(503, json={"error": {"message": "overloaded", "type": "service_unavailable_error",
                                                    "code": "server_is_overloaded", "param": None}})
    if kind == "error_after_reasoning":
        q = response("queued", [])
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse([
            {"type": "response.created", "sequence_number": 0, "response": q},
            {"type": "response.queued", "sequence_number": 1, "response": q},
            {"type": "response.output_item.added", "sequence_number": 2, "output_index": 0,
             "item": {"type": "reasoning", "id": "rs_1", "summary": []}},
            {"type": "error", "sequence_number": 3, "code": "server_error", "message": "boom", "param": None},
        ]))
    text = json.dumps({"sections": [], "overview": []})
    msg = {"type": "message", "id": "m", "role": "assistant", "status": "completed", "phase": "final_answer",
           "content": [{"type": "output_text", "text": text, "annotations": []}]}
    usage = {"input_tokens": 66821, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 9000,
             "output_tokens_details": {"reasoning_tokens": 5600}, "total_tokens": 75821}
    q = response("queued", [])
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse([
        {"type": "response.created", "sequence_number": 0, "response": q},
        {"type": "response.queued", "sequence_number": 1, "response": q},
        {"type": "response.output_item.added", "sequence_number": 2, "output_index": 0, "item": {**msg, "status": "in_progress", "content": []}},
        {"type": "response.output_text.delta", "sequence_number": 3, "item_id": "m", "output_index": 0, "content_index": 0,
         "delta": text[:10], "logprobs": []},
        {"type": "response.completed", "sequence_number": 4, "response": response("completed", [msg], usage)},
    ]))


client = OpenAI(api_key="dummy", base_url="https://mock.invalid/v1", max_retries=0, timeout=180.0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
out = {"openai": openai.__version__}
schema = {"name": "s", "schema": {"type": "object", "additionalProperties": False, "required": ["a"], "properties": {"a": {"type": "string"}}}}
adapter = OpenAIResponses(client, sleep=lambda s: None)
ev = []
t = adapter.turn(instructions="i", history=[{"role": "user", "content": "u"}], tools=[], answer_schema=schema, tool_choice="none",
                 max_output_tokens=16000, safety_identifier="0" * 64, on_event=lambda k, **d: ev.append(k))
out["1_adapter_tools_empty"] = {"wire": seen[-1], "status": t.status, "tier": t.service_tier, "events": ev,
                                "usage": t.usage.__dict__}
s = client.responses.create(model="gpt-5.6-sol", instructions="i", input="u", reasoning={"effort": "low"}, store=False, stream=True,
                            service_tier="flex", prompt_cache_options={"mode": "explicit"}, max_output_tokens=32000,
                            timeout=900.0)
out["2_omitted_flex"] = {"wire": seen[-1], "events": [e.type for e in s]}

MODE["kind"] = "error_after_reasoning"
ev = []
try:
    adapter.turn(instructions="i", history=[], tools=[], answer_schema=schema, tool_choice="none", max_output_tokens=1,
                 safety_identifier="0" * 64, on_event=lambda k, **d: ev.append(k))
except LLMError as exc:
    out["3_stream_error_after_reasoning_item"] = {"notice": exc.notice.kind, "events": ev,
                                                  "requests_sent": sum(1 for _ in seen) - 2}
for kind in ("429_long_retry_after", "503"):
    MODE["kind"] = kind
    try:
        client.responses.create(model="gpt-5.6-sol", input="u", service_tier="flex")
    except openai.APIError as exc:
        n = notice_for_exception(exc)
        out[f"4_{kind}"] = {"exc": type(exc).__name__, "status": exc.status_code, "code": exc.code, "notice": n.kind,
                            "retry_delays": [retry_delay_s(exc, a) for a in range(2)]}
(HERE / "wire_recheck_output.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print(json.dumps(out, indent=1, default=str))
