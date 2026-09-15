import json

import pytest

from assistant.tools import TOOLS, ToolRunner
from tests.schema_check import strict_schema_problems


def run(runner, name, **args):
    outcome = runner.execute(name, json.dumps(args, ensure_ascii=False))
    return outcome, json.loads(outcome.output)


def test_tools_are_strict_function_tools():
    assert [tool["name"] for tool in TOOLS] == ["search", "read_pages", "get_toc"]
    for tool in TOOLS:
        assert tool["type"] == "function" and tool["strict"] is True
        assert strict_schema_problems(tool["parameters"]) == []


def test_search_returns_compact_korean_json_and_a_summary(qa_corpus):
    outcome, payload = run(ToolRunner(qa_corpus), "search", query="한미 정상회담", years=[2023], k=None)
    assert outcome.ok
    assert "정상회담" in outcome.output and '": ' not in outcome.output
    assert payload["order"] == "score"
    ids = [hit["page_id"] for hit in payload["hits"]]
    assert set(ids) == {"2023-p020L", "2023-p020R", "2023-p190L", "2023-p002R"}
    assert ids[-1] == "2023-p002R"
    assert set(payload["hits"][0]) == {"page_id", "label", "year", "chapter", "section", "is_appendix",
                                       "front_matter", "snippet"}
    assert outcome.summary == '찾기 "한미 정상회담" (2023년치) \u2192 4쪽'


def test_search_coerces_loose_inputs(qa_corpus):
    runner = ToolRunner(qa_corpus)
    _, as_text = run(runner, "search", query="정상회담", years="2024", k="1")
    assert [hit["page_id"] for hit in as_text["hits"]] == ["2024-p020L"]
    _, clamped = run(runner, "search", query="정상", years=None, k=50)
    assert 1 <= len(clamped["hits"]) <= 10


def test_search_reports_years_outside_the_corpus(qa_corpus):
    outcome, payload = run(ToolRunner(qa_corpus), "search", query="한일 관계", years=[2015], k=None)
    assert payload["hits"] == [] and payload["out_of_range_years"] == [2015]
    assert outcome.summary == '찾기 "한일 관계" (2015년치) \u2192 0쪽'


def test_question_year_scope_is_enforced(qa_corpus):
    runner = ToolRunner(qa_corpus, allowed_years=[2023])
    _, found = run(runner, "search", query="정상회담", years=[2023, 2024], k=None)
    assert {hit["year"] for hit in found["hits"]} == {2023}
    assert found["notes"]
    _, read = run(runner, "read_pages", page_ids=["2024-p020L", "2023-p020L"])
    assert read["out_of_scope"] == ["2024-p020L"]
    assert [page["page_id"] for page in read["pages"]] == ["2023-p020L"]
    _, toc = run(runner, "get_toc", year=2024)
    assert toc["out_of_scope"] is True


def test_read_pages_numbers_paragraphs_and_logs_what_was_shown(qa_corpus):
    runner = ToolRunner(qa_corpus)
    outcome, payload = run(runner, "read_pages", page_ids=["2023-p020L", "2023-p020L"])
    assert len(payload["pages"]) == 1
    page = payload["pages"][0]
    assert page["paragraphs"] == {"1": "한\u00b7미 정상회담이 4월 26일 워싱턴에서 열렸다.",
                                  "2": "양국 정상은 확장억제 강화를 위한 워싱턴 선언을 채택하였다."}
    assert runner.shown["2023-p020L"].paragraphs == tuple(page["paragraphs"].values())
    assert runner.shown["2023-p020L"].label == page["label"]
    assert outcome.summary == "쪽 읽기 2023년치 38쪽"
    again, repeat = run(runner, "read_pages", page_ids=["2023-p020L"])
    assert repeat == {"pages": [], "already_read": ["2023-p020L"]}
    assert again.summary == "쪽 읽기 새로 읽은 쪽 없음 (이미 읽은 1쪽 제외)"


def test_read_pages_problems_go_back_to_the_model(qa_corpus):
    runner = ToolRunner(qa_corpus)
    _, payload = run(runner, "read_pages", page_ids=["abcd", "2099-p001L", "2024-p004L"])
    assert payload == {"pages": [], "not_found": ["abcd", "2099-p001L"], "not_citable": ["2024-p004L"]}
    too_many, error = run(runner, "read_pages", page_ids=[f"2023-p{n:03d}L" for n in range(1, 7)])
    assert too_many.ok is False and "5쪽" in error["error"]
    assert too_many.summary == "쪽 읽기 입력 오류"


@pytest.mark.parametrize("name, arguments", [
    ("search", "{not json"),
    ("search", '{"years": null, "k": null}'),
    ("search", '["한미"]'),
    ("get_toc", '{"year": "이천이십삼"}'),
    ("delete_everything", "{}"),
    ("get_toc", json.dumps({"year": chr(0x00B2)})),
    ("get_toc", json.dumps({"year": chr(0x0662) + chr(0x0660) + chr(0x0662) + chr(0x0663)})),
    ("search", json.dumps({"query": "정상회담", "years": [chr(0x00B9)], "k": None})),
    ("search", json.dumps({"query": "정상회담", "years": None, "k": chr(0x00B3)})),
])
def test_bad_calls_become_error_outputs(qa_corpus, name, arguments):
    outcome = ToolRunner(qa_corpus).execute(name, arguments)
    assert outcome.ok is False
    assert set(json.loads(outcome.output)) == {"error"}


def test_get_toc_accepts_a_year_string(qa_corpus):
    outcome, payload = run(ToolRunner(qa_corpus), "get_toc", year="2023")
    assert payload["entries"][0]["title"] == "한반도 평화"
    assert outcome.summary == "목차 보기 2023년치"
    _, missing = run(ToolRunner(qa_corpus), "get_toc", year=2012)
    assert missing["not_in_corpus"] is True


def test_lone_surrogates_in_tool_calls_leave_encodable_summaries(qa_corpus):
    runner = ToolRunner(qa_corpus)
    outcome = runner.execute("search", json.dumps({"query": chr(0xD800) + "정상회담", "years": None, "k": None}))
    assert outcome.ok and "정상회담" in outcome.summary
    outcome.summary.encode("utf-8")
    unknown = runner.execute("search" + chr(0xDC00), "{}")
    assert unknown.ok is False
    unknown.summary.encode("utf-8")
