"""The only module that imports the OpenAI SDK (spec 3.1). One streamed Responses API turn -> TurnResult.

Decisions from the groundwork (docs/research/2026-09-15-openai-groundwork/README.md):
- O1 Responses API; O2 stream=True and store=False, every output item replayed by the loop;
- O3 the final response comes from the completed / incomplete / failed event, never output_text;
- O6 strict JSON answer format on every turn; O12 no SDK retries, at most 2 app retries before any output;
- O13 safety_identifier on every request, moderation for the visitor's question only.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import openai
from openai import OpenAI

from assistant.errors import (LLMError, notice_for_exception, notice_for_stream_error, retry_delay_s,
                              stream_retry_delay_s)
from assistant.llm import EventSink, ToolCall, TurnResult, Usage

MODEL = "gpt-5.6-sol"
REASONING = {"effort": "low"}
TIMEOUT_S = 180.0
MODERATION_MODEL = "omni-moderation-latest"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
TERMINAL_EVENTS = ("response.completed", "response.incomplete", "response.failed")


class StreamBroken(Exception):
    """The stream sent an `error` event (code may be None) or ended without a final event."""

    def __init__(self, code: str | None):
        super().__init__(code or "stream ended")
        self.code = code


def load_api_key(env_file: Path = ENV_FILE) -> str:
    """OPENAI_API_KEY from the environment (Hugging Face Secrets) or the local .env. The value is never printed."""
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if value:
        return value
    if Path(env_file).is_file():
        for raw in Path(env_file).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            name, sep, rest = line.partition("=")
            if sep and not line.startswith("#") and name.strip() == "OPENAI_API_KEY":
                rest = rest.strip().strip('"').strip("'")
                if rest:
                    return rest
    raise RuntimeError("OPENAI_API_KEY가 없습니다. .env 파일이나 환경 변수에 넣어 주세요.")


class OpenAIResponses:
    def __init__(self, client: OpenAI | None = None, *, model: str = MODEL, sleep=time.sleep):
        self.client = client if client is not None else OpenAI(api_key=load_api_key(), max_retries=0,
                                                                timeout=TIMEOUT_S)
        self.model = model
        self._sleep = sleep

    def user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def tool_output(self, call_id: str, output: str) -> dict:
        return {"type": "function_call_output", "call_id": call_id, "output": output}

    def turn(self, *, instructions: str, history: list[dict], tools: list[dict], answer_schema: dict,
             tool_choice: str, max_output_tokens: int, safety_identifier: str, on_event: EventSink) -> TurnResult:
        request = dict(
            model=self.model, instructions=instructions, input=history, tools=tools, tool_choice=tool_choice,
            text={"format": {"type": "json_schema", "name": answer_schema["name"], "strict": True,
                             "schema": answer_schema["schema"]}},
            reasoning=REASONING, max_output_tokens=max_output_tokens, store=False, stream=True,
            safety_identifier=safety_identifier,
        )
        attempt = 0
        while True:
            shown = False

            def emit(kind: str, **data) -> None:
                nonlocal shown
                shown = True
                on_event(kind, **data)

            try:
                return self._stream(request, emit)
            except StreamBroken as exc:  # an `error` event, or the stream ended without a final event
                notice = notice_for_stream_error(exc.code)
                delay = None if shown else stream_retry_delay_s(exc.code, attempt)
            except openai.APIError as exc:
                notice = notice_for_exception(exc, output_already_shown=shown)
                delay = None if shown else retry_delay_s(exc, attempt)
            if delay is None:
                raise LLMError(notice)
            attempt += 1
            on_event("retrying", attempt=attempt, delay_s=round(delay, 1))
            self._sleep(delay)

    def moderate(self, text: str) -> list[str]:
        """Flagged category names for the visitor's question; [] when the check itself fails (it never blocks)."""
        try:
            result = self.client.moderations.create(model=MODERATION_MODEL, input=text).results[0]
        except openai.APIError:
            return []
        return sorted(name for name, flagged in result.categories.to_dict().items() if flagged is True)

    def _stream(self, request: dict, emit: EventSink) -> TurnResult:
        final = None
        finished_items: dict[int, object] = {}
        stream = self.client.responses.create(**request)
        try:
            for event in stream:
                kind = event.type
                if kind == "response.output_item.added":
                    item = event.item
                    if item.type == "reasoning":
                        emit("thinking")
                    elif item.type == "function_call":
                        emit("tool_requested", name=item.name)
                    elif item.type == "message" and getattr(item, "phase", None) != "commentary":
                        emit("answer_started")
                elif kind == "response.output_item.done":
                    finished_items[event.output_index] = event.item
                elif kind in TERMINAL_EVENTS:
                    final = event.response
                elif kind == "error":
                    raise StreamBroken(getattr(event, "code", None))
        finally:
            stream.close()
        if final is None:
            raise StreamBroken(None)
        items = list(final.output or []) or [finished_items[i] for i in sorted(finished_items)]
        return _turn_result(final, items)


def _turn_result(response, items: list) -> TurnResult:
    calls: list[ToolCall] = []
    texts: list[str] = []
    refusal = None
    for item in items:
        if item.type == "function_call":
            calls.append(ToolCall(item.call_id, item.name, item.arguments or ""))
        elif item.type == "message" and getattr(item, "phase", None) != "commentary":
            for part in item.content or []:
                if part.type == "output_text":
                    texts.append(part.text)
                elif part.type == "refusal" and refusal is None:
                    refusal = part.refusal or ""
    details = getattr(response, "incomplete_details", None)
    error = getattr(response, "error", None)
    return TurnResult(
        status=response.status,
        output_items=[item.to_dict() for item in items],  # API field names; model_dump() would add async_
        tool_calls=calls,
        answer_text="".join(texts),
        refusal=refusal,
        incomplete_reason=getattr(details, "reason", None),
        error_code=getattr(error, "code", None),
        usage=_usage(response.usage),
        model=response.model or "",
        service_tier=getattr(response, "service_tier", None),
    )


def _usage(usage) -> Usage:
    if usage is None:
        return Usage()
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return Usage(input=usage.input_tokens or 0,
                 cached=getattr(input_details, "cached_tokens", 0) or 0,
                 cache_write=getattr(input_details, "cache_write_tokens", 0) or 0,
                 output=usage.output_tokens or 0,
                 reasoning=getattr(output_details, "reasoning_tokens", 0) or 0)
