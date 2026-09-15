"""A scripted, slow stand-in for the model (no network): the real runner, loop, tools and citation check run
on a made-up corpus, and the fake model pauses the way a streamed turn does so the UI sees real event kinds
spread over time."""
from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

from assistant.corpus import Corpus
from tests.corpus_factory import QA_PAGES, QA_TOC, write_corpus
from tests.fake_llm import FakeLLM, answer_turn, call, tool_turn

HOSTILE = ("<img src=x onerror=\"window.__xss_answer=1\"> ${window.__xss_tpl=1} `${window.__xss_tick=1}` "
           "[link](javascript:alert(1)) **bold** ![t](http://127.0.0.1:7999/answer-md.png)")
HOSTILE_QUERY = ("![t](http://127.0.0.1:7999/query-md.png) <img src=\"http://127.0.0.1:7999/query-html.png\" "
                 "onerror=\"window.__xss_query=1\"> ${window.__xss_tpl_q=1} <script>window.__xss_script=1</script>")

GOOD = {"status": "answered", "sentences": [
    {"text": "정상회담은 4월 26일 워싱턴에서 열렸습니다.",
     "citations": [{"page_id": "2023-p020L", "paragraph": 1, "quote": "4월 26일 워싱턴에서 열렸다"}]},
    {"text": "8월 18일 캠프 데이비드에서 한미일 정상회의가 열렸습니다.",
     "citations": [{"page_id": "2023-p020R", "paragraph": 1, "quote": "캠프 데이비드에서 한미일 정상회의가"}]},
    {"text": HOSTILE, "citations": [{"page_id": "2023-p020L", "paragraph": 2, "quote": "이 구절은 문단에 없습니다 진짜로"}]},
]}


class SlowFakeLLM(FakeLLM):
    """FakeLLM that spreads each turn over turn_s seconds and emits answer_started like the real adapter."""

    def __init__(self, *script, turn_s: float = 1.2, **kw):
        super().__init__(*script, **kw)
        self.turn_s = turn_s

    def turn(self, **request):
        on_event = request["on_event"]
        self.requests.append({**request, "history": list(request["history"])})
        step = self.script.pop(0)
        time.sleep(self.turn_s * 0.3)
        on_event("thinking")
        time.sleep(self.turn_s * 0.4)
        for tool_call in step.tool_calls:
            on_event("tool_requested", name=tool_call.name)
        if not step.tool_calls:
            on_event("answer_started")
        time.sleep(self.turn_s * 0.3)
        return step


def qa_script(turn_s: float = 1.2) -> SlowFakeLLM:
    return SlowFakeLLM(
        tool_turn(call("get_toc", year=2023)),
        tool_turn(call("search", query=HOSTILE_QUERY, years=[2023], k=3)),
        tool_turn(call("search", query="한미 정상회담", years=[2023], k=5)),
        tool_turn(call("read_pages", page_ids=["2023-p020L", "2023-p020R"])),
        answer_turn(GOOD),
        turn_s=turn_s,
    )


@lru_cache(maxsize=1)
def fake_corpus() -> Corpus:
    folder = Path(__file__).resolve().parent / "_corpus"
    return Corpus(write_corpus(folder, QA_PAGES, QA_TOC))
