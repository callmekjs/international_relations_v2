"""Prototype for Plan 3: turn model / corpus / visitor text into safe screen HTML and safe CSV.

Why: gr.HTML inserts its value with innerHTML and the 6.27.0 frontend bundle for it contains no sanitizer
(report 3.1), so every string that did not come from our own code must be escaped. Links are never taken
from model output; the only links are the fixed MOFA board pages below.

Run: python render_safety.py   (self-test, prints a summary)
"""
from __future__ import annotations

import csv
import html
import io
import re

MOFA_BOARD = "https://www.mofa.go.kr/www/brd/m_4105/list.do"
MOFA_VIEW = "https://www.mofa.go.kr/www/brd/m_4105/view.do?seq={seq}"
MOFA_SEQ = {2020: 291, 2021: 292, 2022: 298, 2023: 299, 2024: 300, 2025: 301}   # verified 2026-09-15
BADGE_CLASS = {"확인됨": "ok", "문단만 확인": "warn", "근거 없음": "none"}
AI_LABEL = "AI 생성"


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def mofa_link(year: int | None) -> str:
    seq = MOFA_SEQ.get(year) if isinstance(year, int) else None
    return MOFA_VIEW.format(seq=seq) if seq else MOFA_BOARD


def progress_line(event: dict) -> str:
    kind = event.get("event")
    if kind == "tool_finished":
        mark = "✓" if event.get("ok") else "⚠"
        return f'<li class="step">{mark} {esc(event.get("summary"))}</li>'   # summary holds the model's search words
    if kind == "tool_skipped":
        return f'<li class="step">✗ 도구 한도에 닿아 건너뜀 ({esc(event.get("name"))})</li>'
    if kind == "thinking":
        return '<li class="step">… 생각 중</li>'
    if kind == "answer_started":
        return '<li class="step">… 답 정리 중</li>'
    if kind == "retrying":
        return f'<li class="step">↻ 다시 시도 {esc(event.get("attempt"))}번째</li>'
    return ""


def answer_html(answer: dict | None, notice: dict | None) -> str:
    parts = ['<section class="answer">', f'<span class="ai-label">{AI_LABEL}</span>']
    for sentence in (answer or {}).get("sentences", []):
        refs = "".join(f"<sup>[{int(n)}]</sup>" for n in sentence.get("refs", []) if isinstance(n, int))
        badge = sentence.get("badge", "근거 없음")
        parts.append(f'<p class="s {BADGE_CLASS.get(badge, "none")}">{esc(sentence.get("text"))}{refs}</p>')
    references = (answer or {}).get("references", [])
    if references:
        parts.append('<ol class="refs">')
        for ref in references:
            year = _year(ref.get("page_id"))
            badge = ref.get("badge", "근거 없음")
            parts.append(
                f'<li value="{int(ref.get("n", 0))}">{esc(ref.get("label"))} {esc(ref.get("paragraph"))}문단 '
                f'<q>{esc(ref.get("quote"))}</q> <span class="badge {BADGE_CLASS.get(badge, "none")}">{esc(badge)}</span> '
                f'<a href="{esc(mofa_link(year))}" target="_blank" rel="noopener noreferrer">외교부 원문</a></li>')
        parts.append("</ol>")
    if notice:
        parts.append(f'<p class="notice">{esc(notice.get("message"))}</p>')
    parts.append("</section>")
    return "".join(parts)


def _year(page_id) -> int | None:
    match = re.match(r"^(\d{4})-p", str(page_id or ""))
    return int(match.group(1)) if match else None


_FORMULA_START = tuple("=+-@\t\r\n") + ("＝", "＋", "－", "＠")
_PLAIN_NUMBER = re.compile(r"^-?\d[\d,]*(\.\d+)?%?$")


def csv_cell(value) -> str:
    """OWASP CSV-injection rule: a cell that could start a formula gets a leading apostrophe.
    Plain numbers such as -3.5% stay numbers."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_START) and not _PLAIN_NUMBER.match(text):
        return "'" + text
    return text


def table_csv(columns: list[str], rows: list[list], *, model: str) -> bytes:
    """UTF-8 with BOM (Excel), every cell quoted, AI label inside the file itself (it leaves the service)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow([f"{AI_LABEL} 표 · 외교백서 AI 조수 ({model}) · 원문과 대조해 사용하세요"])
    writer.writerow([])
    writer.writerow([csv_cell(c) for c in columns])
    for row in rows:
        writer.writerow([csv_cell(c) for c in row])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


if __name__ == "__main__":
    attacks = ['<img src=x onerror=alert(1)>', '</p><script>alert(1)</script>', '[눌러](javascript:alert(1))',
               '![](https://attacker.example/pixel.png)', '" onmouseover="alert(1)', "<a href='https://evil.example'>공식</a>"]
    answer = {"sentences": [{"text": a, "refs": [1], "badge": "확인됨"} for a in attacks],
              "references": [{"n": 1, "page_id": "2023-p050L", "label": attacks[0], "paragraph": attacks[4],
                              "quote": attacks[1], "badge": "문단만 확인"}]}
    out = answer_html(answer, {"message": attacks[5]}) + progress_line({"event": "tool_finished", "ok": True,
                                                                         "summary": attacks[0]})
    from html.parser import HTMLParser

    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.seen = []

        def handle_starttag(self, tag, attrs):
            self.seen.append((tag, tuple(sorted(name for name, _ in attrs))))

    parser = Tags()
    parser.feed(out)
    allowed = {"section", "span", "p", "sup", "ol", "li", "q", "a"}
    allowed_attrs = {"class", "value", "href", "target", "rel"}
    assert all(tag in allowed and set(attrs) <= allowed_attrs for tag, attrs in parser.seen), parser.seen
    assert "<img" not in out and "<script" not in out
    assert out.count("<a ") == 1 and 'href="https://www.mofa.go.kr/www/brd/m_4105/view.do?seq=299"' in out
    cells = ["=HYPERLINK(\"http://x\")", "+1+1", "-3.5%", "@SUM(A1)", "＝1+1", "1,234", "한미 정상회담"]
    safe = [csv_cell(c) for c in cells]
    assert safe == ["'=HYPERLINK(\"http://x\")", "'+1+1", "-3.5%", "'@SUM(A1)", "'＝1+1", "1,234", "한미 정상회담"], safe
    data = table_csv(["날짜", "내용"], [["2023.4.26", "=cmd|' /C calc'!A0"]], model="gpt-5.6-sol")
    assert data.startswith(b"\xef\xbb\xbf") and b"'=cmd" in data
    print({"html_attacks_escaped": len(attacks), "tags_rendered": sorted({t for t, _ in parser.seen}), "only_link": mofa_link(2023), "csv_cells": safe,
           "csv_bytes": len(data)})
    print("ALL PASSED")
