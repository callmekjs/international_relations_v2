import json
import sys
import types

import pytest

from assistant import Result, run
from assistant.errors import BILLING, LLMError
from assistant.limits import QA_CAPS
from assistant.prompts import QA_INSTRUCTIONS
from assistant.runner import hash_identifier
from tests.fake_llm import FakeLLM, answer_turn, call, tool_turn

QUESTION = "2023년 한미 정상회담은 어디서 열렸어?"
GOOD = {"status": "answered", "sentences": [
    {"text": "정상회담은 4월 26일 워싱턴에서 열렸습니다.",
     "citations": [{"page_id": "2023-p020L", "paragraph": 1, "quote": "4월 26일 워싱턴에서 열렸다"}]},
    {"text": "양국은 공동 성명을 냈습니다.",
     "citations": [{"page_id": "2023-p020L", "paragraph": 2, "quote": "양국 정상은 공동 성명을 발표하였다"}]},
]}


def test_qa_run_checks_evidence_and_keeps_a_replayable_record(qa_corpus):
    llm = FakeLLM(tool_turn(call("search", query="한미 정상회담", years=[2023], k=None)),
                  tool_turn(call("read_pages", page_ids=["2023-p020L"])),
                  answer_turn(GOOD))
    seen = []
    result = run("qa", {"question": QUESTION, "years": [2023]}, lambda kind, **data: seen.append(kind),
                 llm=llm, corpus=qa_corpus)
    assert isinstance(result, Result)
    assert (result.status, result.notice) == ("answered", None)
    assert [s["badge"] for s in result.answer["sentences"]] == ["확인됨", "문단만 확인"]
    assert result.answer["references"][0]["label"] == qa_corpus.label(qa_corpus.pages["2023-p020L"])
    assert llm.moderated == [QUESTION]
    first = llm.requests[0]
    assert first["instructions"] == QA_INSTRUCTIONS
    assert first["history"][0]["content"].endswith("(연도 범위: 2023년치)")
    assert len(first["safety_identifier"]) == 64
    assert (result.usage["turns"], result.usage["tool_calls"]) == (3, 2) and result.usage["cost_krw"] > 0
    assert seen[-1] == "done" and "tool_finished" in seen
    record = json.loads(json.dumps(result.record, ensure_ascii=False))
    assert record["inputs"] == {"question": QUESTION, "years": [2023]}
    assert record["events"][-1] == {"event": "done", "status": "answered"}
    assert record["answer_raw"] == GOOD and record["turns"][0]["usage"]["input"] == 2_000
    assert record["model"] == "gpt-5.6-sol" and record["prompt_version"].startswith("qa-")


def test_flagged_question_is_refused_before_the_model_runs(qa_corpus):
    llm = FakeLLM(flagged=["sexual/minors"])
    result = run("qa", {"question": "부적절한 질문"}, llm=llm, corpus=qa_corpus)
    assert (result.status, result.notice["kind"]) == ("refused", "moderation_flagged")
    assert llm.requests == [] and result.usage["cost_krw"] == 0


@pytest.mark.parametrize("question, kind", [("   ", "empty_question"), ("가" * 301, "question_too_long")])
def test_bad_questions_stop_before_any_call(qa_corpus, question, kind):
    llm = FakeLLM()
    result = run("qa", {"question": question}, llm=llm, corpus=qa_corpus)
    assert (result.status, result.notice["kind"]) == ("error", kind)
    assert llm.moderated == [] and llm.requests == []


def test_budget_error_is_shown_as_a_notice(qa_corpus):
    result = run("qa", {"question": QUESTION}, llm=FakeLLM(LLMError(BILLING)), corpus=qa_corpus)
    assert (result.status, result.answer) == ("error", None)
    assert result.notice == {"kind": "budget", "message": BILLING.message}
    assert result.record["events"][-2]["event"] == "notice"


def test_answer_after_the_tool_cap_says_the_search_was_cut_short(qa_corpus):
    searches = [tool_turn(call("search", query=f"정상회담 {n}", years=None, k=1)) for n in range(QA_CAPS.tool_calls)]
    not_found = {"status": "not_found", "sentences": [{"text": "백서에서 찾지 못했어요.", "citations": []}]}
    llm = FakeLLM(*searches, answer_turn(not_found))
    result = run("qa", {"question": "정상회담은 몇 번 열렸어?"}, llm=llm, corpus=qa_corpus)
    assert llm.requests[-1]["tool_choice"] == "none"
    assert (result.status, result.notice["kind"]) == ("not_found", "cap_reached")


def test_only_qa_exists_yet(qa_corpus):
    with pytest.raises(ValueError):
        run("table", {"question": "표"}, llm=FakeLLM(), corpus=qa_corpus)


def test_safety_identifier_is_a_salted_hash():
    assert len(hash_identifier("1.2.3.4|UA")) == 64
    assert hash_identifier("1.2.3.4|UA", "a") != hash_identifier("1.2.3.4|UA", "b")


@pytest.mark.parametrize("years", ["2023", ["20x3"], [True], [2023.0], [None], {"2023": True},
                                   [chr(0x0662) + chr(0x0660) + chr(0x0662) + chr(0x0663)]])
def test_bad_years_stop_before_any_call(qa_corpus, years):
    llm = FakeLLM()
    result = run("qa", {"question": QUESTION, "years": years}, llm=llm, corpus=qa_corpus)
    assert (result.status, result.notice["kind"]) == ("error", "bad_years")
    assert llm.moderated == [] and llm.requests == []
    json.dumps(result.record, ensure_ascii=False)


def test_years_may_be_numbers_or_digit_strings(qa_corpus):
    llm = FakeLLM(answer_turn(GOOD))
    result = run("qa", {"question": QUESTION, "years": ["2023", " 2024 ", 2023]}, llm=llm, corpus=qa_corpus)
    assert result.record["inputs"]["years"] == [2023, 2024]
    assert result.record["error"] is None


def test_a_missing_api_key_is_a_setup_notice_with_a_record(qa_corpus, monkeypatch):
    class NoKey:
        def __init__(self):
            raise RuntimeError("OPENAI_API_KEY가 없습니다.")

    adapter = types.ModuleType("assistant.llm_openai")
    adapter.OpenAIResponses = NoKey
    monkeypatch.setitem(sys.modules, "assistant.llm_openai", adapter)
    result = run("qa", {"question": QUESTION}, corpus=qa_corpus)
    assert (result.status, result.notice["kind"]) == ("error", "config_error")
    assert result.record["error"] == "RuntimeError: OPENAI_API_KEY가 없습니다."
    assert result.record["events"][-1] == {"event": "done", "status": "error"}
    json.dumps(result.record, ensure_ascii=False)


def test_a_missing_corpus_is_a_setup_notice(monkeypatch):
    def no_corpus():
        raise FileNotFoundError("corpus/pages.jsonl")

    monkeypatch.setattr("assistant.runner.default_corpus", no_corpus)
    llm = FakeLLM()
    result = run("qa", {"question": QUESTION}, llm=llm)
    assert (result.status, result.notice["kind"]) == ("error", "config_error")
    assert result.record["error"] == "FileNotFoundError: corpus/pages.jsonl" and llm.requests == []


class ModerationDown(FakeLLM):
    def moderate(self, text: str) -> list[str]:
        raise ConnectionError("moderation down")


def test_crashes_while_moderating_running_or_verifying_return_a_result(qa_corpus, monkeypatch):
    down = run("qa", {"question": QUESTION}, llm=ModerationDown(), corpus=qa_corpus)
    assert (down.status, down.notice["kind"], down.record["error"]) == ("error", "unknown",
                                                                        "ConnectionError: moderation down")
    crashed = run("qa", {"question": QUESTION}, llm=FakeLLM(tool_turn(call("get_toc", year=2023)),
                                                           ValueError("x" * 400)), corpus=qa_corpus)
    assert (crashed.status, crashed.notice["kind"]) == ("error", "unknown")
    assert crashed.record["error"] == "ValueError: " + "x" * 300
    assert len(crashed.record["turns"]) == 1 and crashed.usage["turns"] == 1 and crashed.usage["cost_krw"] > 0

    def broken_verify(answer, shown):
        raise KeyError("sentences")

    monkeypatch.setattr("assistant.runner.verify_answer", broken_verify)
    unverified = run("qa", {"question": QUESTION}, llm=FakeLLM(answer_turn(GOOD)), corpus=qa_corpus)
    assert (unverified.status, unverified.notice["kind"], unverified.answer) == ("error", "unknown", None)
    assert unverified.record["error"] == "KeyError: 'sentences'" and len(unverified.record["turns"]) == 1
    assert unverified.record["answer_raw"] == GOOD
    json.loads(json.dumps(unverified.record, ensure_ascii=False))
