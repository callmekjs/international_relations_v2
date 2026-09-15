import json

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
