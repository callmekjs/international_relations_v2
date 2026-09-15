"""The tool-using loop for one question (spec 3.2, 4.3, 4.4). Provider-neutral: it talks to an LLM
object, runs tools, enforces the caps and returns the model's final JSON unjudged; the citations
are checked afterwards by the runner."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from assistant.errors import BAD_ANSWER, CAP_STOPPED, UNKNOWN, LLMError, UserNotice, error_text, notice_for_turn
from assistant.limits import Budget, Caps
from assistant.llm import LLM, EventSink, Usage
from assistant.pricing import cost_usd
from assistant.prompts import STATUSES
from assistant.textnorm import utf8_safe
from assistant.tools import TOOLS, ToolRunner

SKIPPED_OUTPUT = json.dumps({"error": "도구 사용 한도에 닿아 실행하지 않았습니다. 이미 읽은 내용으로 답하세요."},
                            ensure_ascii=False, separators=(",", ":"))


@dataclass
class TurnRecord:
    n: int
    tool_choice: str
    max_output_tokens: int
    status: str
    items: list[str]          # output item kinds, e.g. "reasoning", "function_call", "message:final_answer"
    usage: Usage
    model: str
    service_tier: str | None
    cost_usd: float
    tool_calls: list[dict] = field(default_factory=list)
    price_model: str = ""     # the model name the cost was priced with; "" when no price was found


@dataclass
class LoopOutcome:
    answer: dict | None
    notice: UserNotice | None
    forced_answer: bool       # a cap blocked tools (or stopped the run) before the model answered
    turns: list[TurnRecord]
    error: str | None = None  # "ExceptionType: message" when an unexpected exception ended the run


def run_agent(llm: LLM, runner: ToolRunner, *, instructions: str, user_text: str, answer_format: dict,
              caps: Caps, safety_identifier: str, on_event: EventSink) -> LoopOutcome:
    budget = Budget(caps)
    turns: list[TurnRecord] = []
    forced = False
    try:
        history: list[dict] = [llm.user_message(user_text)]
        added_chars = len(instructions) + len(user_text) + len(_dumps(TOOLS)) + len(_dumps(answer_format))
        while True:
            plan = budget.plan_next_turn(added_chars)
            if not plan.send:
                return LoopOutcome(None, CAP_STOPPED, True, turns)
            forced = forced or plan.tool_choice == "none"
            try:
                turn = llm.turn(instructions=instructions, history=history, tools=TOOLS, answer_schema=answer_format,
                                tool_choice=plan.tool_choice, max_output_tokens=plan.max_output_tokens,
                                safety_identifier=safety_identifier, on_event=on_event)
            except LLMError as exc:
                return LoopOutcome(None, exc.notice, forced, turns)
            budget.record_turn(turn.usage)
            model = turn.model or llm.model
            cost, price_model = turn_cost(turn.usage, (model, llm.model), turn.service_tier)
            record = TurnRecord(len(turns) + 1, plan.tool_choice, plan.max_output_tokens, turn.status,
                                _item_kinds(turn.output_items), turn.usage, model, turn.service_tier, cost,
                                price_model=price_model)
            turns.append(record)
            history.extend(turn.output_items)
            notice = notice_for_turn(turn)
            if notice is not None:
                return LoopOutcome(None, notice, forced, turns)
            if not turn.tool_calls:
                answer = parse_answer(turn.answer_text)
                return LoopOutcome(answer, None if answer is not None else BAD_ANSWER, forced, turns)
            if plan.tool_choice == "none":
                return LoopOutcome(None, BAD_ANSWER, forced, turns)
            added_chars = 0
            for tool_call in turn.tool_calls:  # parallel calls each count as one tool call
                if budget.tool_calls_left() > 0:
                    budget.record_tool_call()
                    try:
                        outcome = runner.execute(tool_call.name, tool_call.arguments)
                    except Exception:  # keep the call on record, then end the run below
                        record.tool_calls.append({"name": tool_call.name, "arguments": tool_call.arguments,
                                                  "summary": None, "ok": False, "output_chars": 0,
                                                  "skipped": False})
                        raise
                    output = outcome.output
                    on_event("tool_finished", name=tool_call.name, summary=outcome.summary, ok=outcome.ok)
                    record.tool_calls.append({"name": tool_call.name, "arguments": tool_call.arguments,
                                              "summary": outcome.summary, "ok": outcome.ok,
                                              "output_chars": len(output), "skipped": False})
                else:
                    output = SKIPPED_OUTPUT
                    on_event("tool_skipped", name=tool_call.name)
                    record.tool_calls.append({"name": tool_call.name, "arguments": tool_call.arguments,
                                              "summary": None, "ok": False, "output_chars": len(output),
                                              "skipped": True})
                history.append(llm.tool_output(tool_call.call_id, output))  # every call needs an output
                added_chars += len(output)
    except Exception as exc:  # a crash (in the adapter, a tool, ...) must not lose the turns already paid for
        return LoopOutcome(None, UNKNOWN, forced, turns, error=error_text(exc))


def turn_cost(usage: Usage, models: tuple[str, ...], service_tier: str | None) -> tuple[float, str]:
    """(cost in USD, model name it was priced with). Tries each name in turn (the returned model, then the
    requested one) and records 0 with "" when none has a price, so pricing never ends a paid run."""
    for name in models:
        try:
            return round(cost_usd(usage, name, service_tier), 6), name
        except Exception:
            continue
    return 0.0, ""


def parse_answer(text: str) -> dict | None:
    """The final JSON answer, or None when it is not the agreed shape. Lone surrogates become '?' so the
    answer can be printed and kept in a UTF-8 record."""
    try:
        answer = utf8_safe(json.loads(text))
    except (json.JSONDecodeError, TypeError, RecursionError):
        return None
    if (not isinstance(answer, dict) or answer.get("status") not in STATUSES
            or not isinstance(answer.get("sentences"), list)):
        return None
    for sentence in answer["sentences"]:
        if (not isinstance(sentence, dict) or not isinstance(sentence.get("text"), str)
                or not isinstance(sentence.get("citations"), list)
                or not all(isinstance(citation, dict) for citation in sentence["citations"])):
            return None
    return answer


def _item_kinds(items: list[dict]) -> list[str]:
    kinds = []
    for item in items:
        kind = str(item.get("type", "?"))
        if kind == "message" and item.get("phase"):
            kind += ":" + str(item["phase"])
        kinds.append(kind)
    return kinds


def _dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
