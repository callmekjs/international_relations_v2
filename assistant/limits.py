"""Per-run caps (spec 4.4). The loop asks the budget before every model turn (groundwork O4):
tools stay allowed only while there is still room for one more turn that must answer."""
from __future__ import annotations

import math
from dataclasses import dataclass

from assistant.llm import Usage

TOKENS_PER_CHAR = 1.0      # deliberately high: white-paper text measured 0.64 tokens per character
NEXT_TURN_GROWTH = 16_000  # one read_pages of 5 pages (at most about 7,100 tokens) plus one turn's output


@dataclass(frozen=True)
class Caps:
    tool_calls: int
    input_tokens: int     # summed over every turn of the run
    output_tokens: int    # summed over every turn, reasoning included
    output_per_call: int  # max_output_tokens of one turn


QA_CAPS = Caps(tool_calls=10, input_tokens=120_000, output_tokens=30_000, output_per_call=8_000)


@dataclass(frozen=True)
class TurnPlan:
    send: bool
    tool_choice: str  # "auto" or "none"
    max_output_tokens: int


class Budget:
    def __init__(self, caps: Caps):
        self.caps = caps
        self.tool_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._last_input = 0
        self._last_output = 0

    def record_turn(self, usage: Usage) -> None:
        self.input_tokens += usage.input
        self.output_tokens += usage.output
        self._last_input, self._last_output = usage.input, usage.output

    def record_tool_call(self) -> None:
        self.tool_calls += 1

    def tool_calls_left(self) -> int:
        return max(0, self.caps.tool_calls - self.tool_calls)

    def plan_next_turn(self, added_chars: int) -> TurnPlan:
        """added_chars: text added to the conversation since the last turn (first turn: everything sent).
        The next request resends the whole conversation, so it is at least as big as the last one."""
        estimate = self._last_input + self._last_output + math.ceil(added_chars * TOKENS_PER_CHAR)
        input_left = self.caps.input_tokens - self.input_tokens
        output_left = self.caps.output_tokens - self.output_tokens
        if estimate > input_left or output_left <= 0:
            return TurnPlan(False, "none", 0)
        tools_allowed = (self.tool_calls_left() > 0
                         and 2 * estimate + NEXT_TURN_GROWTH <= input_left
                         and output_left >= 2 * self.caps.output_per_call)
        return TurnPlan(True, "auto" if tools_allowed else "none", min(self.caps.output_per_call, output_left))
