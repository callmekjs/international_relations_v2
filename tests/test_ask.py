import json
import os
import subprocess
import sys

import pytest

from assistant.ask import format_event, main, turn_table
from assistant.errors import BILLING, LLMError
from assistant.llm import ToolCall
from assistant.runner import ROOT
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


def test_lone_surrogates_in_the_model_json_cannot_make_a_record_unwritable(qa_corpus, tmp_path, capsys):
    escape = chr(92) + "ud800"  # the model may write this escape; json.loads turns it into a lone surrogate
    search = ToolCall("call_s1", "search", json.dumps({"query": chr(0xD800) + "정상회담", "years": None, "k": None}))
    answer = json.dumps(ANSWER, ensure_ascii=False).replace("워싱턴에서", "워싱턴" + escape + "에서", 1)  # text, not quote
    llm = FakeLLM(tool_turn(search, call("read_pages", page_ids=["2023-p020L"])), answer_turn(answer))
    code = main(["2023년 한미 정상회담은 어디서 열렸어?"], llm=llm, corpus=qa_corpus, out_dir=tmp_path)
    assert code == 0
    assert "워싱턴?에서 열렸습니다. [1] (확인됨)" in capsys.readouterr().out
    record = json.loads(next(tmp_path.glob("*-qa.json")).read_text(encoding="utf-8"))
    assert record["answer_raw"]["sentences"][0]["text"] == "워싱턴?에서 열렸습니다."
    assert record["answer"]["sentences"][0]["text"] == "워싱턴?에서 열렸습니다."


def test_events_without_a_line_are_silent():
    assert format_event("tool_requested", {"name": "search"}) is None
    assert format_event("done", {"status": "answered"}) is None
    assert format_event("tool_finished", {"name": "search", "summary": "찾기", "ok": True}).endswith("찾기")


def test_a_notice_is_printed_once_and_the_time_is_shown(qa_corpus, tmp_path, capsys):
    assert format_event("notice", {"notice": "budget", "message": BILLING.message}) is None
    code = main(["2023년 한미 정상회담은 어디서 열렸어?"], llm=FakeLLM(LLMError(BILLING)), corpus=qa_corpus,
                out_dir=tmp_path)
    out = capsys.readouterr().out
    assert code == 1 and out.count(BILLING.message) == 1 and f"안내: {BILLING.message}" in out
    record = json.loads(next(tmp_path.glob("*-qa.json")).read_text(encoding="utf-8"))
    assert f"{record['elapsed_s']}초" in out


@pytest.mark.parametrize("years", ["2023,이천", "2023," + chr(0x0662) + chr(0x0660) + chr(0x0662) + chr(0x0663)])
def test_non_numeric_years_are_a_usage_error(qa_corpus, tmp_path, capsys, years):
    llm, runs = FakeLLM(), tmp_path / "runs"  # qa_corpus already lives in tmp_path / "corpus"
    with pytest.raises(SystemExit) as caught:
        main(["2023년 한미 정상회담은 어디서 열렸어?", "--years", years], llm=llm, corpus=qa_corpus, out_dir=runs)
    assert caught.value.code == 2 and "--years" in capsys.readouterr().err
    assert llm.moderated == [] and not runs.exists()


def test_a_missing_table_file_is_a_usage_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--table", str(tmp_path / "none.json")])
    assert caught.value.code == 2 and "기록 파일" in capsys.readouterr().err


def test_terminal_errors_are_utf8_even_on_a_narrow_console(tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "ascii"}
    done = subprocess.run([sys.executable, "-m", "assistant.ask", "--table", str(tmp_path / "none.json")],
                          cwd=ROOT, capture_output=True, env=env, timeout=120)
    assert done.returncode == 2
    assert "기록 파일" in done.stderr.decode("utf-8")
