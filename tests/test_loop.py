import json

import pytest

from assistant.errors import ANSWER_CUT, BAD_ANSWER, BILLING, CAP_STOPPED, UNKNOWN, LLMError
from assistant.limits import QA_CAPS, Caps
from assistant.llm import TurnResult, Usage
from assistant.loop import TurnRecord, parse_answer, run_agent
from assistant.prompts import QA_ANSWER_FORMAT, QA_INSTRUCTIONS
from assistant.tools import ToolRunner
from tests.fake_llm import FakeLLM, answer_turn, call, tool_turn

ANSWER = {"status": "answered", "sentences": [{"text": "워싱턴에서 열렸습니다.", "citations": [
    {"page_id": "2023-p020L", "paragraph": 1, "quote": "4월 26일 워싱턴에서 열렸다"}]}]}


def caps(**changes):
    values = {"tool_calls": 10, "input_tokens": 120_000, "output_tokens": 30_000, "output_per_call": 8_000, **changes}
    return Caps(**values)


def ask(llm, corpus, *, limits=QA_CAPS, seen=None, runner=None):
    runner = runner or ToolRunner(corpus)
    events = seen if seen is not None else []
    return run_agent(llm, runner, instructions=QA_INSTRUCTIONS, user_text="2023년 한미 정상회담은 어디서 열렸어?",
                     answer_format=QA_ANSWER_FORMAT, caps=limits, safety_identifier="a" * 64,
                     on_event=lambda kind, **data: events.append((kind, data)))


def test_search_read_answer(qa_corpus):
    llm = FakeLLM(tool_turn(call("search", query="한미 정상회담", years=[2023], k=None)),
                  tool_turn(call("read_pages", page_ids=["2023-p020L"])),
                  answer_turn(ANSWER))
    runner, seen = ToolRunner(qa_corpus), []
    outcome = ask(llm, qa_corpus, runner=runner, seen=seen)
    assert (outcome.answer, outcome.notice, outcome.forced_answer) == (ANSWER, None, False)
    assert [turn.items for turn in outcome.turns] == [["reasoning", "function_call"], ["reasoning", "function_call"],
                                                      ["message:final_answer"]]
    assert "2023-p020L" in runner.shown
    kinds = [item.get("type", item.get("role")) for item in llm.requests[2]["history"]]
    assert kinds == ["user", "reasoning", "function_call", "function_call_output",
                     "reasoning", "function_call", "function_call_output"]
    assert [r["tool_choice"] for r in llm.requests] == ["auto", "auto", "auto"]
    assert [r["max_output_tokens"] for r in llm.requests] == [8_000, 8_000, 8_000]
    assert [data["summary"] for kind, data in seen if kind == "tool_finished"] == [
        '찾기 "한미 정상회담" (2023년치) \u2192 4쪽', "쪽 읽기 2023년치 38쪽"]
    assert all(turn.cost_usd > 0 for turn in outcome.turns)


def test_parallel_calls_count_and_the_cap_forces_an_answer(qa_corpus):
    llm = FakeLLM(tool_turn(call("search", query="정상회담", years=None, k=None), call("get_toc", year=2023)),
                  answer_turn(ANSWER))
    outcome = ask(llm, qa_corpus, limits=caps(tool_calls=2))
    assert [r["tool_choice"] for r in llm.requests] == ["auto", "none"]
    assert outcome.forced_answer is True and outcome.answer == ANSWER


def test_calls_beyond_the_cap_are_answered_without_running(qa_corpus):
    llm = FakeLLM(tool_turn(call("search", query="정상회담", years=None, k=None), call("get_toc", year=2023)),
                  answer_turn(ANSWER))
    seen = []
    outcome = ask(llm, qa_corpus, limits=caps(tool_calls=1), seen=seen)
    outputs = [item for item in llm.requests[1]["history"] if item.get("type") == "function_call_output"]
    assert len(outputs) == 2 and "한도" in json.loads(outputs[1]["output"])["error"]
    assert [kind for kind, _ in seen if kind in ("tool_finished", "tool_skipped")] == ["tool_finished", "tool_skipped"]
    assert [c["skipped"] for c in outcome.turns[0].tool_calls] == [False, True]


def test_tool_calls_when_tools_are_blocked_end_the_run(qa_corpus):
    llm = FakeLLM(tool_turn(call("search", query="정상회담", years=None, k=None)))
    outcome = ask(llm, qa_corpus, limits=caps(tool_calls=0))
    assert llm.requests[0]["tool_choice"] == "none"
    assert outcome.notice is BAD_ANSWER and outcome.answer is None


def test_cut_turns_and_llm_errors_become_notices(qa_corpus):
    cut = TurnResult("incomplete", [{"type": "reasoning"}], [], "", incomplete_reason="max_output_tokens",
                     usage=Usage(input=1_000, output=8_000), model="gpt-5.6-sol")
    assert ask(FakeLLM(cut), qa_corpus).notice is ANSWER_CUT
    assert ask(FakeLLM(LLMError(BILLING)), qa_corpus).notice is BILLING


def test_bad_final_json_is_a_notice(qa_corpus):
    assert ask(FakeLLM(answer_turn("{broken")), qa_corpus).notice is BAD_ANSWER


@pytest.mark.parametrize("text", [
    "not json", '{"status": "maybe", "sentences": []}', '{"status": "answered"}', "[]",
    '{"status": "answered", "sentences": ["워싱턴"]}',
    '{"status": "answered", "sentences": [{"text": 1, "citations": []}]}',
    '{"status": "answered", "sentences": [{"text": "워싱턴"}]}',
    '{"status": "answered", "sentences": [{"text": "워싱턴", "citations": "2023-p020L"}]}',
    '{"status": "answered", "sentences": [{"text": "워싱턴", "citations": ["2023-p020L"]}]}',
])
def test_malformed_answers_are_rejected(text):
    assert parse_answer(text) is None


def test_deeply_nested_json_is_rejected_instead_of_raising():
    assert parse_answer("[" * 100_000) is None
    assert parse_answer('{"status": "answered", "sentences": ' + "[" * 100_000) is None


def test_well_formed_answers_pass_the_shape_check():
    assert parse_answer(json.dumps(ANSWER, ensure_ascii=False)) == ANSWER
    empty = {"status": "not_found", "sentences": [{"text": "찾지 못했어요.", "citations": []}]}
    assert parse_answer(json.dumps(empty, ensure_ascii=False)) == empty


def test_nothing_is_sent_when_even_the_first_turn_is_over_the_cap(qa_corpus):
    llm = FakeLLM()
    outcome = ask(llm, qa_corpus, limits=caps(input_tokens=1_000))
    assert llm.requests == [] and outcome.notice is CAP_STOPPED


def answer_as(model: str) -> TurnResult:
    return TurnResult("completed", [], [], json.dumps(ANSWER, ensure_ascii=False),
                      usage=Usage(input=1_000, output=100), model=model)


def test_turn_cost_uses_the_returned_model_then_the_requested_one_and_never_raises(qa_corpus):
    known = ask(FakeLLM(answer_as("gpt-5.6-sol-2026-08-01")), qa_corpus).turns[0]
    assert (known.price_model, known.cost_usd > 0) == ("gpt-5.6-sol-2026-08-01", True)
    renamed = ask(FakeLLM(answer_as("gpt-next-preview")), qa_corpus)
    assert renamed.answer == ANSWER
    assert (renamed.turns[0].model, renamed.turns[0].price_model) == ("gpt-next-preview", "gpt-5.6-sol")
    assert renamed.turns[0].cost_usd == known.cost_usd
    unpriced = FakeLLM(answer_as("mystery-a"))
    unpriced.model = "mystery-b"
    turn = ask(unpriced, qa_corpus).turns[0]
    assert (turn.cost_usd, turn.price_model) == (0, "")
    assert TurnRecord(1, "auto", 8_000, "completed", [], Usage(), "m", None, 0.0).price_model == ""


class CrashingRunner(ToolRunner):
    def execute(self, name: str, arguments: str):
        raise OSError("디스크 오류")


def test_unexpected_crashes_end_the_run_but_keep_the_paid_turns(qa_corpus):
    crash = ask(FakeLLM(tool_turn(call("get_toc", year=2023)), RuntimeError("x" * 500)), qa_corpus)
    assert (crash.answer, crash.notice, len(crash.turns)) == (None, UNKNOWN, 1)
    assert crash.error == "RuntimeError: " + "x" * 300
    tool_crash = ask(FakeLLM(tool_turn(call("get_toc", year=2023))), qa_corpus, runner=CrashingRunner(qa_corpus))
    assert (tool_crash.notice, len(tool_crash.turns), tool_crash.error) == (UNKNOWN, 1, "OSError: 디스크 오류")
    assert tool_crash.turns[0].cost_usd > 0
    assert [(c["name"], c["ok"], c["skipped"]) for c in tool_crash.turns[0].tool_calls] == [("get_toc", False, False)]
    assert ask(FakeLLM(answer_turn(ANSWER)), qa_corpus).error is None
