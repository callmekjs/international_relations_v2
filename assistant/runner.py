"""assistant.run(task, inputs, on_event) -> Result (spec 3.1). Plan 2 builds the qa task.

The record keeps everything needed to replay the run in the UI (example gallery) and to grade it:
inputs, progress events, per-turn usage and cost, the model's raw answer and the checked answer.
Encrypted reasoning is not kept."""
from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from assistant.citations import verify_answer
from assistant.corpus import Corpus
from assistant.errors import CAP_REACHED, EMPTY_QUESTION, QUESTION_TOO_LONG, UserNotice, notice_for_moderation
from assistant.limits import QA_CAPS
from assistant.llm import LLM, EventSink, Usage
from assistant.loop import TurnRecord, run_agent
from assistant.pricing import krw
from assistant.prompts import QA_ANSWER_FORMAT, QA_INSTRUCTIONS, QA_PROMPT_VERSION, qa_user_text
from assistant.tools import ToolRunner

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "corpus"
MAX_QUESTION_CHARS = 300
RECORD_VERSION = 1


@dataclass
class Result:
    task: str
    status: str          # answered | not_found | not_in_corpus | refused | partial | error
    answer: dict | None  # verify_answer() output
    notice: dict | None  # {"kind", "message"}
    usage: dict
    record: dict         # JSON-serialisable


def hash_identifier(source: str, salt: str = "") -> str:
    """64-character safety_identifier (groundwork O13): never the raw visitor data."""
    return hashlib.sha256(f"{salt}|{source}".encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def default_corpus() -> Corpus:
    return Corpus(CORPUS_DIR)


def usage_summary(turns: list[TurnRecord]) -> dict:
    tokens = sum((turn.usage for turn in turns), Usage())
    cost = sum(turn.cost_usd for turn in turns)
    return {"turns": len(turns),
            "tool_calls": sum(1 for turn in turns for c in turn.tool_calls if not c["skipped"]),
            "tokens": asdict(tokens), "cost_usd": round(cost, 6), "cost_krw": krw(cost)}


def run(task: str, inputs: dict, on_event: EventSink | None = None, *, llm: LLM | None = None,
        corpus: Corpus | None = None, safety_identifier: str | None = None) -> Result:
    if task != "qa":
        raise ValueError(f"아직 만들지 않은 기능입니다: {task}")
    started = time.perf_counter()
    events: list[dict] = []

    def emit(kind: str, **data) -> None:
        events.append({"event": kind, **data})
        if on_event is not None:
            on_event(kind, **data)

    question = str(inputs.get("question") or "").strip()
    years = sorted({int(year) for year in inputs.get("years") or []}) or None
    record = {"version": RECORD_VERSION, "task": task,
              "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "prompt_version": QA_PROMPT_VERSION, "inputs": {"question": question, "years": years}}

    def finish(status: str, notice: UserNotice | None, turns: list[TurnRecord], model: str | None,
               answer: dict | None = None, answer_raw: dict | None = None) -> Result:
        if notice is not None:
            emit("notice", notice=notice.kind, message=notice.message)
        emit("done", status=status)
        usage = usage_summary(turns)
        record.update(model=model, status=status, notice=notice.to_dict() if notice else None, events=events,
                      turns=[asdict(turn) for turn in turns], answer_raw=answer_raw, answer=answer, usage=usage,
                      elapsed_s=round(time.perf_counter() - started, 2))
        return Result(task, status, answer, notice.to_dict() if notice else None, usage, record)

    if not question:
        return finish("error", EMPTY_QUESTION, [], None)
    if len(question) > MAX_QUESTION_CHARS:
        return finish("error", QUESTION_TOO_LONG, [], None)
    if llm is None:
        from assistant.llm_openai import OpenAIResponses  # the SDK loads only when a real run needs it
        llm = OpenAIResponses()
    blocked = notice_for_moderation(llm.moderate(question))
    if blocked is not None:
        return finish(blocked.status, blocked, [], llm.model)
    runner = ToolRunner(corpus if corpus is not None else default_corpus(), years)
    outcome = run_agent(llm, runner, instructions=QA_INSTRUCTIONS, user_text=qa_user_text(question, years),
                        answer_format=QA_ANSWER_FORMAT, caps=QA_CAPS,
                        safety_identifier=safety_identifier or hash_identifier("local"), on_event=emit)
    if outcome.answer is None:
        return finish(outcome.notice.status, outcome.notice, outcome.turns, llm.model)
    answer = verify_answer(outcome.answer, runner.shown)
    notice = outcome.notice or (CAP_REACHED if outcome.forced_answer else None)
    return finish(answer["status"], notice, outcome.turns, llm.model, answer, outcome.answer)
