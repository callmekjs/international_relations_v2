"""Live progress for a first-time summary: turn streamed answer text (response.output_text.delta) into
"section n of m" events without parsing incomplete JSON. No network; the self-test feeds a synthetic answer
in random chunk sizes.

    PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe progress_proto.py
"""
from __future__ import annotations

import json
import random
import re
from typing import Callable

_TITLE = re.compile(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"')
_TEXT_KEY = re.compile(r'"text"\s*:')
_OVERVIEW = re.compile(r'"overview"\s*:')


class SummaryProgress:
    """Feed answer-text deltas; calls emit(kind, **data) once per new section, once for the overview, and every
    `every` sentences. The strict schema fixes key order (sections first, title before sentences), so a regex
    over the accumulated text is enough."""

    def __init__(self, emit: Callable[..., None], total_sections: int, total_sentences: int, every: int = 5):
        self.emit, self.total_sections, self.total_sentences, self.every = emit, total_sections, total_sentences, every
        self.text = ""
        self.sections = 0
        self.sentences = 0
        self.overview = False

    def feed(self, delta: str) -> None:
        self.text += delta
        titles = [json.loads(f'"{m.group(1)}"') for m in _TITLE.finditer(self.text)]
        for n in range(self.sections, len(titles)):
            self.emit("section_started", n=n + 1, of=self.total_sections, title=titles[n])
        self.sections = len(titles)
        count = len(_TEXT_KEY.findall(self.text))
        if count // self.every > self.sentences // self.every:
            self.emit("sentences_written", count=count, of=self.total_sentences)
        self.sentences = count
        if not self.overview and _OVERVIEW.search(self.text):
            self.overview = True
            self.emit("overview_started")


def _self_test() -> dict:
    answer = {"sections": [{"title": f"제{i}절 시험 \"따옴표\" 제목", "sentences": [
        {"text": f"문장 {i}-{j}", "citations": [{"page_id": "2023-p050L", "paragraph": 1, "quote": "가" * 20}]}
        for j in range(4)]} for i in range(1, 7)],
        "overview": [{"text": "개요", "citations": [{"page_id": "2023-p050L", "paragraph": 1, "quote": "나" * 20}]}]}
    text = json.dumps(answer, ensure_ascii=False, separators=(",", ":"))
    rng = random.Random(7)
    events: list[tuple] = []
    progress = SummaryProgress(lambda kind, **d: events.append((kind, d)), total_sections=6, total_sentences=25)
    i = 0
    while i < len(text):
        step = rng.randint(1, 9)  # deltas can split keys, escapes and Hangul syllables' JSON anywhere
        progress.feed(text[i:i + step])
        i += step
    kinds = [k for k, _ in events]
    assert kinds.count("section_started") == 6, kinds
    assert [d["n"] for k, d in events if k == "section_started"] == [1, 2, 3, 4, 5, 6]
    assert kinds.count("overview_started") == 1
    return {"chars": len(text), "events": [(k, d) for k, d in events]}


if __name__ == "__main__":
    print(json.dumps(_self_test(), ensure_ascii=False, indent=1))
