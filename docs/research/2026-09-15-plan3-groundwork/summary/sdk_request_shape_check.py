"""No-network check of what openai==3.14.0 puts on the wire for a summary request, and how the existing
adapter (assistant/llm_openai.py, read-only import) handles a flex response and a flex 429.

A MockTransport answers every request locally; the API key is a dummy string, nothing reaches OpenAI.

    PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe sdk_request_shape_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx2
import openai
from openai import OpenAI

REPO = Path("C:/international_relations")
sys.path.insert(0, str(REPO))  # read-only import of assistant.*; PYTHONDONTWRITEBYTECODE keeps the repo untouched

from assistant.errors import BUSY, notice_for_exception, retry_delay_s  # noqa: E402
from assistant.llm_openai import OpenAIResponses  # noqa: E402  (client is injected: load_api_key is never called)

OUT = Path(__file__).with_name("sdk_request_shape_check_output.json")
captured: list[dict] = []
ANSWER = {"status": "answered", "sections": []}


def sse(events: list[dict]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events).encode()


def completed_stream(service_tier: str) -> bytes:
    response = {"id": "resp_mock", "object": "response", "created_at": 0, "model": "gpt-5.6-sol",
                "status": "completed", "service_tier": service_tier, "tools": [], "tool_choice": "auto",
                "parallel_tool_calls": True,
                "output": [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                            "phase": "final_answer",
                            "content": [{"type": "output_text", "text": json.dumps(ANSWER), "annotations": []}]}],
                "usage": {"input_tokens": 71000, "input_tokens_details": {"cached_tokens": 0},
                          "output_tokens": 6000, "output_tokens_details": {"reasoning_tokens": 1500},
                          "total_tokens": 77000}}
    queued = {**response, "status": "queued", "output": [], "usage": None}
    return sse([{"type": "response.created", "sequence_number": 0, "response": queued},
                {"type": "response.queued", "sequence_number": 1, "response": queued},
                {"type": "response.output_item.added", "sequence_number": 2, "output_index": 0,
                 "item": {"type": "message", "id": "msg_1", "role": "assistant", "status": "in_progress",
                          "phase": "final_answer", "content": []}},
                {"type": "response.completed", "sequence_number": 3, "response": response}])


MODE = {"status": 200}


def handler(request: httpx2.Request) -> httpx2.Response:
    body = json.loads(request.content.decode("utf-8"))
    captured.append({"path": request.url.path, "body_keys": sorted(body), "tools": body.get("tools", "<absent>"),
                     "tool_choice": body.get("tool_choice", "<absent>"),
                     "service_tier": body.get("service_tier", "<absent>"),
                     "prompt_cache_options": body.get("prompt_cache_options", "<absent>")})
    if MODE["status"] == 429:
        return httpx2.Response(429, json={"error": {"message": "Resource unavailable (mock)", "type": "rate_limit_error",
                                                    "code": "resource_unavailable", "param": None}})
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=completed_stream("flex"))


def main() -> None:
    client = OpenAI(api_key="dummy-not-a-key", base_url="https://mock.invalid/v1", max_retries=0,
                    http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    results: dict = {"openai_version": openai.__version__, "httpx2_version": httpx2.__version__}

    # 1. The current adapter always passes tools and tool_choice: what does tools=[] send?
    adapter = OpenAIResponses(client)
    events: list[str] = []
    schema = {"name": "chapter_summary", "schema": {"type": "object", "additionalProperties": False,
                                                    "required": ["status"], "properties": {"status": {"type": "string"}}}}
    turn = adapter.turn(instructions="x", history=[{"role": "user", "content": "y"}], tools=[], answer_schema=schema,
                        tool_choice="none", max_output_tokens=16000, safety_identifier="0" * 64,
                        on_event=lambda kind, **d: events.append(kind))
    results["adapter_tools_empty"] = {"wire": captured[-1], "turn_status": turn.status,
                                      "service_tier_seen": turn.service_tier, "usage": turn.usage.__dict__,
                                      "answer_text": turn.answer_text, "events": events}

    # 2. Omitting tools / tool_choice entirely, with flex and explicit cache mode (what Plan 3 should send)
    stream = client.responses.create(model="gpt-5.6-sol", instructions="x", input=[{"role": "user", "content": "y"}],
                                     text={"format": {"type": "json_schema", **schema, "strict": True}},
                                     reasoning={"effort": "low"}, max_output_tokens=24000, store=False, stream=True,
                                     service_tier="flex", prompt_cache_options={"mode": "explicit"},
                                     safety_identifier="0" * 64)
    kinds = [event.type for event in stream]
    results["omitted_tools_flex"] = {"wire": captured[-1], "event_types": kinds}

    # 3. A flex 429 through the existing error mapping (the code string is a guess: the docs only say "429 Resource Unavailable")
    MODE["status"] = 429
    try:
        client.responses.create(model="gpt-5.6-sol", input="y", service_tier="flex", stream=True)
    except openai.APIError as exc:
        notice = notice_for_exception(exc)
        results["flex_429"] = {"exception": type(exc).__name__, "status": getattr(exc, "status_code", None),
                               "code": getattr(exc, "code", None), "notice_kind": notice.kind,
                               "is_BUSY": notice is BUSY, "app_retry": notice.app_retry,
                               "retry_delays_s": [retry_delay_s(exc, attempt) for attempt in range(3)]}
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
