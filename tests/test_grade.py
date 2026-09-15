from assistant.runner import run
from evals.grade import grade, render_report, summarize
from evals.run_gold import main, run_gold
from tests.fake_llm import FakeLLM, answer_turn, call, tool_turn

FACT = {"id": "g99", "kind": "multi_year", "question": "q", "years": None, "expect_status": "answered",
        "facts": [["257건"], ["334명"]], "gold_pages": ["2020-p150R", "2021-p106R"], "absent_terms": []}
REFUSE = {"id": "g98", "kind": "refused", "question": "코드 짜 줘", "years": None, "expect_status": "refused",
          "facts": [], "gold_pages": [], "absent_terms": []}


def record(status, sentences, references):
    answer = {"sentences": sentences, "references": references} if sentences is not None else None
    return {"status": status, "answer": answer, "elapsed_s": 12.5,
            "usage": {"cost_krw": 250, "tokens": {"input": 20_000, "cached": 0, "cache_write": 0,
                                                 "output": 3_000, "reasoning": 2_000}}}


def sentence(text, grade_name="verified", reasons=("exact",)):
    return {"text": text, "grade": grade_name, "badge": "", "refs": [1],
            "citations": [{"grade": grade_name, "reason": reason} for reason in reasons]}


VERIFIED_GOLD = [{"n": 1, "page_id": "2020-p150R", "paragraph": 3, "label": "", "quote": "", "grade": "verified",
                  "badge": "", "corrected": None}]


def test_fact_answer_passes_with_facts_and_a_verified_gold_page():
    row = grade(FACT, record("answered", [sentence("2020년에는 257건을 지원했습니다."),
                                          sentence("2021년에는 334 명이 영주귀국했습니다.")], VERIFIED_GOLD))
    assert row["passed"] is True and row["reasons"] == []
    assert (row["cost_krw"], row["elapsed_s"], row["grades"]) == (250, 12.5, {"verified": 2})


def test_missing_fact_wrong_page_wrong_status_and_invented_pages_fail():
    wrong_page = [{**VERIFIED_GOLD[0], "page_id": "2020-p001L"}]
    row = grade(FACT, record("not_found", [sentence("257건을 지원했습니다.", reasons=("exact", "page_not_read"))],
                             wrong_page))
    assert row["passed"] is False
    assert len(row["reasons"]) == 4
    assert any("334명" in reason for reason in row["reasons"])


def test_refusal_passes_without_an_answer_body():
    assert grade(REFUSE, record("refused", None, None))["passed"] is True


def test_summary_and_report():
    rows = [grade(FACT, record("answered", [sentence("257건, 334명")], VERIFIED_GOLD)),
            grade(REFUSE, record("error", None, None))]
    summary = summarize(rows)
    assert (summary["passed"], summary["total"], summary["cost_krw"]) == (1, 2, 500)
    assert summary["by_kind"] == {"multi_year": {"passed": 1, "total": 1}, "refused": {"passed": 0, "total": 1}}
    report = render_report(summary, rows, "시험")
    assert report.startswith("# 시험") and "| g99 | multi_year | O |" in report and "| g98 | refused | X |" in report


def test_run_gold_writes_records_and_a_report(qa_corpus, tmp_path):
    fact = {"id": "g01", "kind": "single_page", "question": "2024년 신속해외송금 지원은 몇 건이었어?", "years": [2024],
            "expect_status": "answered", "facts": [["257건"]], "gold_pages": ["2024-p020L"], "absent_terms": []}
    answer = {"status": "answered", "sentences": [{"text": "2024년 신속해외송금 지원은 257건이었습니다.", "citations": [
        {"page_id": "2024-p020L", "paragraph": 2, "quote": "신속해외송금 지원 실적은 257건"}]}]}
    refusal = {"status": "refused", "sentences": [{"text": "외교백서에 관한 질문만 답할 수 있어요.", "citations": []}]}
    llm = FakeLLM(tool_turn(call("read_pages", page_ids=["2024-p020L"])), answer_turn(answer), answer_turn(refusal))
    out_dir = tmp_path / "gold"  # qa_corpus already lives in tmp_path / "corpus"
    summary = run_gold([fact, REFUSE], llm=llm, corpus=qa_corpus, out_dir=out_dir)
    assert (summary["passed"], summary["total"]) == (2, 2)
    assert sorted(p.name for p in out_dir.iterdir()) == ["g01.json", "g98.json", "report.md"]


def test_run_gold_needs_confirmation(capsys):
    assert main([]) == 2
    assert "--confirm" in capsys.readouterr().out


def test_run_gold_keeps_going_when_one_question_crashes(qa_corpus, tmp_path, capsys):
    def flaky(task, inputs, **options):
        if inputs["question"] == FACT["question"]:
            raise RuntimeError("boom")
        return run(task, inputs, **options)

    refusal = {"status": "refused", "sentences": [{"text": "외교백서에 관한 질문만 답할 수 있어요.", "citations": []}]}
    out_dir = tmp_path / "gold"
    summary = run_gold([FACT, REFUSE], llm=FakeLLM(answer_turn(refusal)), corpus=qa_corpus, out_dir=out_dir, ask=flaky)
    assert (summary["passed"], summary["total"]) == (1, 2)
    assert summary["by_kind"]["multi_year"] == {"passed": 0, "total": 1}
    report = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "| g99 | multi_year | X | error | 0 | 0 | 0 | 0 | 실행 오류: RuntimeError |" in report
    assert "g99 X error" in capsys.readouterr().out
