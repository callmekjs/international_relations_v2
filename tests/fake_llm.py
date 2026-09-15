"""A scripted stand-in for the model, for tests that must never call the API."""
from __future__ import annotations

import itertools
import json

from assistant.llm import ToolCall, TurnResult, Usage

MODEL = "gpt-5.6-sol"
_ids = itertools.count(1)


def call(name: str, **arguments) -> ToolCall:
    return ToolCall(f"call_{next(_ids)}", name, json.dumps(arguments, ensure_ascii=False))


def tool_turn(*calls: ToolCall, usage: Usage = Usage(input=2_000, output=300, reasoning=200)) -> TurnResult:
    items = [{"type": "reasoning", "id": "rs", "summary": [], "encrypted_content": "ENC"}]
    items += [{"type": "function_call", "call_id": c.call_id, "name": c.name, "arguments": c.arguments} for c in calls]
    return TurnResult("completed", items, list(calls), "", usage=usage, model=MODEL)


def answer_turn(answer, usage: Usage = Usage(input=4_000, output=500, reasoning=300)) -> TurnResult:
    text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
    items = [{"type": "message", "phase": "final_answer", "content": [{"type": "output_text", "text": text}]}]
    return TurnResult("completed", items, [], text, usage=usage, model=MODEL)


class FakeLLM:
    model = MODEL

    def __init__(self, *script, flagged=()):
        self.script = list(script)
        self.flagged = list(flagged)
        self.requests: list[dict] = []
        self.moderated: list[str] = []

    def user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def tool_output(self, call_id: str, output: str) -> dict:
        return {"type": "function_call_output", "call_id": call_id, "output": output}

    def turn(self, **request) -> TurnResult:
        self.requests.append({**request, "history": list(request["history"])})
        if not self.script:
            raise AssertionError("FakeLLM: no scripted turn left")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        request["on_event"]("thinking")
        for tool_call in step.tool_calls:
            request["on_event"]("tool_requested", name=tool_call.name)
        return step

    def moderate(self, text: str) -> list[str]:
        self.moderated.append(text)
        return list(self.flagged)
