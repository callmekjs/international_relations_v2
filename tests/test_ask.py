import json

from assistant.ask import format_event, main, turn_table
from tests.fake_llm import FakeLLM, answer_turn, call, tool_turn

ANSWER = {"status": "answered", "sentences": [{"text": "워싱턴에서 열렸습니다.", "citations": [
    {"page_id": "2023-p020L", "paragraph": 1, "quote": "4월 26일 워싱턴에서 열렸다"}]}]}


def test_cli_prints_progress_answer_and_saves_the_record(qa_corpus, tmp_path, capsys):
    llm = FakeLLM(tool_turn(call("read_pages", page_ids=["2023-p020L"])), answer_turn(ANSWER))
    code = main(["2023년 한미 정상회담은 어디서 열렸어?", "--years", "2023"], llm=llm, corpus=qa_corpus, out_dir=tmp_path)
    out = capsys.readouterr().out
    assert code == 0
    assert "쪽 읽기 2023년치 38쪽" in out
    assert "워싱턴에서 열렸습니다. [1] (확인됨)" in out
    assert "1문단 '4월 26일 워싱턴에서 열렸다'" in out
    assert "상태: answered" in out and "원" in out
    saved = list(tmp_path.glob("*-qa.json"))
    assert len(saved) == 1

    code = main(["--table", str(saved[0])])
    table = capsys.readouterr().out
    assert code == 0 and "| 1 | auto | reasoning, function_call |" in table
    assert turn_table(json.loads(saved[0].read_text(encoding="utf-8"))).count("\n") == 3


def test_events_without_a_line_are_silent():
    assert format_event("tool_requested", {"name": "search"}) is None
    assert format_event("done", {"status": "answered"}) is None
    assert format_event("tool_finished", {"name": "search", "summary": "찾기", "ok": True}).endswith("찾기")
