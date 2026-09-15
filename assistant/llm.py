"""Provider-neutral view of one model turn (spec 3.1). The loop, tools, limits and pricing use only
these types; assistant/llm_openai.py is the one file that knows the OpenAI SDK."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

EventSink = Callable[..., None]  # on_event(kind: str, **data)


@dataclass(frozen=True)
class Usage:
    input: int = 0        # every input token, cached and cache-write tokens included
    cached: int = 0
    cache_write: int = 0
    output: int = 0       # every generated token, reasoning included
    reasoning: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.input + other.input, self.cached + other.cached, self.cache_write + other.cache_write,
                     self.output + other.output, self.reasoning + other.reasoning)


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: str  # JSON text as the model wrote it


@dataclass
class TurnResult:
    status: str                  # "completed" | "incomplete" | "failed"
    output_items: list[dict]     # sent back verbatim on the next turn
    tool_calls: list[ToolCall]
    answer_text: str             # final-answer message text; commentary messages are left out
    refusal: str | None = None
    incomplete_reason: str | None = None
    error_code: str | None = None
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    service_tier: str | None = None


class LLM(Protocol):
    model: str

    def user_message(self, text: str) -> dict: ...

    def tool_output(self, call_id: str, output: str) -> dict: ...

    def turn(self, *, instructions: str, history: list[dict], tools: list[dict], answer_schema: dict,
             tool_choice: str, max_output_tokens: int, safety_identifier: str,
             on_event: EventSink) -> TurnResult: ...

    def moderate(self, text: str) -> list[str]: ...
