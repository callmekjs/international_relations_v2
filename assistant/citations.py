"""Checks the model's evidence against the paragraphs it was shown (spec 4.2.1). No LLM, no network.

A citation is page_id + paragraph number + a short quote copied from that paragraph. Quotes are
compared in cite_key() form: match_key() plus folding of dash, quote-mark, tilde and bracket
variants. Dots and dashes between digits become one separator instead of disappearing, and a quote
may not start or end inside a longer number (groundwork O7). There is no "almost the same" grade:
in the groundwork 447 of 449 meaning flips passed such a rule (O5).

Special characters are written as \\uXXXX escapes on purpose (docs/에러노트.md, 2026-09-15).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Mapping

from assistant.textnorm import match_key, normalize

MIN_QUOTE_CHARS = 12
VERIFIED, PARAGRAPH_ONLY, UNSUPPORTED = "verified", "paragraph_only", "unsupported"
GRADE_RANK = {VERIFIED: 2, PARAGRAPH_ONLY: 1, UNSUPPORTED: 0}
BADGES = {VERIFIED: "확인됨", PARAGRAPH_ONLY: "문단만 확인", UNSUPPORTED: "근거 없음"}
CORRECTION_LABELS = {"paragraph": "문단 바로잡음", "page": "쪽 바로잡음"}
_PAGE_ID = re.compile(r"^([0-9]{4})-p[0-9]{3}[LR]$")


@dataclass(frozen=True)
class ShownPage:
    """A page as read_pages showed it to the model; paragraph numbers start at 1."""
    page_id: str
    year: int
    label: str
    paragraphs: tuple[str, ...]


# --- comparison key --------------------------------------------------------------------------
_DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe63\uff0d"
_QUOTES = ("'\"`\u00b4\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u2032\u2033\u2035\u2036"
           "\u300c\u300d\u300e\u300f\u3008\u3009\u300a\u300b\u00ab\u00bb<>")
_TILDES = "~\u223c\uff5e\u301c"
_SIGN_SENTINEL = "\ue000"       # private-use characters that normalize() and match_key() leave alone
_DIGIT_SEP_SENTINEL = "\ue001"
_ARROW = re.compile("->|=>|\u21d2")
_SIGN = re.compile(r"(?<![^\s(\[{,:;/~])[" + re.escape(_DASHES) + r"](?=\d)")
_DIGIT_SEP = re.compile(r"(?<=[0-9])[" + re.escape(_DASHES + "\u00b7") + r"](?=[0-9])")
_KEY_TABLE: dict[int, str | None] = {ord(c): None for c in _DASHES + _QUOTES + "\u00b7"}
_KEY_TABLE.update({ord(c): "~" for c in _TILDES})
_KEY_TABLE.update({0xff08: "(", 0xff09: ")", 0xff3b: "[", 0xff3d: "]",
                   ord(_SIGN_SENTINEL): "-", ord(_DIGIT_SEP_SENTINEL): "/"})
_QUOTE_EDGES = ".,\u2026\u22ef\u3002"


def _display(text: str) -> str:
    """One-line display form; keyed() positions point into this string."""
    return _ARROW.sub("\u2192", normalize(text))


def _mark(display: str) -> str:
    """Minus signs and separators between digits become one-character sentinels (same length)."""
    return _DIGIT_SEP.sub(_DIGIT_SEP_SENTINEL, _SIGN.sub(_SIGN_SENTINEL, display))


def cite_key(text: str) -> str:
    """match_key() plus variant folding: separator dashes, every middle dot, quote marks and angle
    brackets removed; tildes unified; full-width brackets to ASCII; minus signs and digit separators kept."""
    return match_key(_mark(_display(text))).translate(_KEY_TABLE)


def keyed(text: str) -> tuple[str, str, list[int]]:
    """(display, key, positions): key == cite_key(text) and key[i] came from display[positions[i]]."""
    display = _display(text)
    chars: list[str] = []
    positions: list[int] = []
    for i, ch in enumerate(_mark(display)):
        if ch.isspace():
            continue
        for c in ch.lower():
            mapped = _KEY_TABLE.get(ord(c), c)
            if mapped is None:
                continue
            chars.append(mapped)
            positions.append(i)
    return display, "".join(chars), positions


def _cuts_number(edge: str, display: str, i: int, step: int) -> bool:
    """True when the quote's edge digit continues a longer number in the text (47명 is no evidence for 7명)."""
    if not edge.isdigit() or not 0 <= i < len(display):
        return False
    if display[i].isdigit():
        return True
    j = i + step
    return display[i] in ".," and 0 <= j < len(display) and display[j].isdigit()


def _find(keyed_text: tuple[str, str, list[int]], qkey: str) -> int:
    display, key, positions = keyed_text
    j = key.find(qkey)
    while j >= 0:
        first, last = positions[j], positions[j + len(qkey) - 1]
        if not (_cuts_number(qkey[0], display, first - 1, -1) or _cuts_number(qkey[-1], display, last + 1, 1)):
            return j
        j = key.find(qkey, j + 1)
    return -1


def _span(keyed_text: tuple[str, str, list[int]], start: int, end: int) -> str:
    display, _, positions = keyed_text
    return display[positions[start]:positions[end - 1] + 1]


def _year_of(page_id: str) -> int | None:
    match = _PAGE_ID.match(page_id)
    return int(match.group(1)) if match else None


# --- verification ----------------------------------------------------------------------------
def check_citation(citation: Mapping, shown: Mapping[str, ShownPage]) -> dict:
    page_id = str(citation.get("page_id") or "")
    paragraph = citation.get("paragraph")
    quote = str(citation.get("quote") or "")
    page = shown.get(page_id)
    paragraph_ok = (page is not None and isinstance(paragraph, int) and not isinstance(paragraph, bool)
                    and 1 <= paragraph <= len(page.paragraphs))
    result = {"page_id": page_id, "paragraph": paragraph, "quote": quote, "grade": UNSUPPORTED, "reason": "",
              "found_page_id": None, "found_paragraph": None, "corrected": None, "evidence": None, "label": None}

    qkey = cite_key(quote.strip().strip(_QUOTE_EDGES).strip())
    if len(qkey) < MIN_QUOTE_CHARS:
        return _fallback(result, page, paragraph, paragraph_ok, "quote_too_short")

    candidates: list[tuple[ShownPage, int, str | None, str]] = []
    if paragraph_ok:
        candidates.append((page, paragraph, None, "exact"))
    if page is not None:
        candidates += [(page, n, "paragraph", "moved_paragraph")
                       for n in range(1, len(page.paragraphs) + 1) if n != paragraph]
    year = _year_of(page_id)
    candidates += [(other, n, "page", "moved_page")
                   for other in shown.values() if other.page_id != page_id and other.year == year
                   for n in range(1, len(other.paragraphs) + 1)]
    for found, number, corrected, reason in candidates:
        kt = keyed(found.paragraphs[number - 1])
        j = _find(kt, qkey)
        if j >= 0:
            result.update(grade=VERIFIED, reason=reason, found_page_id=found.page_id, found_paragraph=number,
                          corrected=corrected, evidence=_span(kt, j, j + len(qkey)), label=found.label)
            return result
    return _fallback(result, page, paragraph, paragraph_ok, "quote_not_in_paragraph")


def _fallback(result: dict, page: ShownPage | None, paragraph, paragraph_ok: bool, reason: str) -> dict:
    if paragraph_ok:
        result.update(grade=PARAGRAPH_ONLY, reason=reason, found_page_id=page.page_id,
                      found_paragraph=paragraph, label=page.label)
    else:
        result["reason"] = "page_not_read" if page is None else "no_such_paragraph"
    return result


def verify_answer(answer: Mapping, shown: Mapping[str, ShownPage]) -> dict:
    """Per-sentence grade and badge, plus one numbered reference list shared by all sentences."""
    references: list[dict] = []
    numbers: dict[tuple, int] = {}
    sentences = []
    for sentence in answer.get("sentences") or []:
        checks, seen = [], set()
        for citation in sentence.get("citations") or []:
            ident = (citation.get("page_id"), citation.get("paragraph"), citation.get("quote"))
            if ident in seen:
                continue
            seen.add(ident)
            checks.append(check_citation(citation, shown))
        grade = max((c["grade"] for c in checks), key=GRADE_RANK.__getitem__, default=UNSUPPORTED)
        refs: list[int] = []
        for c in checks:
            if c["grade"] == UNSUPPORTED:
                continue
            quote = c["evidence"] if c["grade"] == VERIFIED else c["quote"]
            key = (c["found_page_id"], c["found_paragraph"], c["grade"], quote)
            if key not in numbers:
                numbers[key] = len(references) + 1
                references.append({"n": numbers[key], "page_id": c["found_page_id"], "paragraph": c["found_paragraph"],
                                   "label": c["label"], "quote": quote, "grade": c["grade"],
                                   "badge": BADGES[c["grade"]], "corrected": c["corrected"]})
            if numbers[key] not in refs:
                refs.append(numbers[key])
        sentences.append({"text": str(sentence.get("text") or ""), "grade": grade, "badge": BADGES[grade],
                          "refs": refs, "citations": checks})
    return {"status": answer.get("status"), "sentences": sentences, "references": references,
            "counts": dict(Counter(s["grade"] for s in sentences))}
