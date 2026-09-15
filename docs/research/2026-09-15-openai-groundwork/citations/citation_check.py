"""Citation verifier prototype (Plan 2 groundwork). Offline: no LLM or network calls.

Recommended answer format (design b, see citations.md): a strict-JSON answer
    {"sentences": [{"text": str, "citations": [{"page_id": str, "quote": str}]}], "status": str}
Each quote must be copied verbatim from a page that read_pages returned in this conversation.

verify_answer() checks every citation:
  (i)   page_id must be among the pages read_pages returned (not search hits, not invented);
  (ii)  the quote must be contained in that page's text, compared with cite_key(): match_key()
        plus a rule for hyphen/dash, middle-dot, quote-mark, tilde and full-width-bracket variants
        (a dash directly before a digit after a space/bracket is kept as a minus sign);
  (iii) sentences without a valid citation get the badge "근거 없음".
Also accepts inline markers (designs a/c) through parse_inline_answer(); those have no quote,
so only the page and the numbers/Latin words of the sentence can be checked.

Special characters are written as \\uXXXX escapes on purpose (docs/에러노트.md, 2026-09-15).
"""
from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

from assistant.textnorm import bigram_tokens, match_key, normalize

# OpenAI-recommended inline citation marker characters (citation-formatting guide).
CITE_START, CITE_DELIM, CITE_STOP = "\ue200", "\ue202", "\ue201"

PAGE_ID_PATTERN = r"^[0-9]{4}-p[0-9]{3}[LR]$"
MIN_QUOTE_KEY = 8          # shorter quotes (after cite_key) prove nothing
NEAR_RATIO = 0.85          # similarity needed for "원문과 조금 다름"
NEAR_MAX_CHANGED = 6       # ... and at most this many changed characters (key form) in total

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sentences", "status"],
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "citations"],
                "properties": {
                    "text": {"type": "string", "description": "답의 한 문장"},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["page_id", "quote"],
                            "properties": {
                                "page_id": {"type": "string", "pattern": PAGE_ID_PATTERN},
                                "quote": {"type": "string",
                                          "description": "그 쪽 원문에서 그대로 복사한 15~100자"},
                            },
                        },
                    },
                },
            },
        },
        "status": {"type": "string", "enum": ["answered", "not_found", "not_in_corpus", "refused"]},
    },
}

GRADE_RANK = {"verified": 3, "near": 2, "page_only": 1, "unsupported": 0}
BADGES = {"verified": "확인됨", "near": "원문과 조금 다름", "page_only": "쪽만 확인", "unsupported": "근거 없음"}

# --- comparison key --------------------------------------------------------------------------
_DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe63\uff0d"
_QUOTES = ("'\"`\u00b4\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u2032\u2033\u2035\u2036"
           "\u300c\u300d\u300e\u300f\u3008\u3009\u300a\u300b\u00ab\u00bb<>")
_TILDES = "~\u223c\uff5e\u301c"
_SIGN_SENTINEL = "\ue000"   # private-use char that normalize()/match_key() leave untouched
_ARROW = re.compile(r"->|=>|\u21d2")
_SIGN = re.compile(rf"(?<![^\s(\[{{,:;/~]){'[' + re.escape(_DASHES) + ']'}(?=\d)")

_KEY_TABLE: dict[int, str | None] = {ord(c): None for c in _DASHES + _QUOTES + "\u00b7"}
_KEY_TABLE.update({ord(c): "~" for c in _TILDES})
_KEY_TABLE.update({0xff08: "(", 0xff09: ")", 0xff3b: "[", 0xff3d: "]", ord(_SIGN_SENTINEL): "-"})


def _display(text: str) -> str:
    """One-line display form; same length as the string the key positions point into."""
    return _ARROW.sub("\u2192", normalize(text))


def cite_key(text: str) -> str:
    """match_key() plus variant folding: dashes used as separators, every '\u00b7', quote marks
    and angle brackets removed; tildes unified; full-width brackets to ASCII; minus signs kept."""
    marked = _SIGN.sub(_SIGN_SENTINEL, _display(text))
    return match_key(marked).translate(_KEY_TABLE)


def keyed(text: str) -> tuple[str, str, list[int]]:
    """(display, key, positions): key == cite_key(text); key[i] came from display[positions[i]]."""
    disp = _display(text)
    marked = _SIGN.sub(_SIGN_SENTINEL, disp)
    chars: list[str] = []
    pos: list[int] = []
    for i, ch in enumerate(marked):
        if ch.isspace():
            continue
        for c in ch.lower():
            mapped = _KEY_TABLE.get(ord(c), c)
            if mapped is None:
                continue
            chars.append(mapped)
            pos.append(i)
    return disp, "".join(chars), pos


def anchors(text: str) -> Counter:
    """Numbers (with minus sign) and Latin words: the parts a light edit must not change."""
    t = _SIGN.sub(_SIGN_SENTINEL, _display(text)).lower()
    t = re.sub("[" + re.escape(_DASHES) + "]", " ", t).replace(_SIGN_SENTINEL, "-")
    return Counter(re.findall(r"-?\d+|[a-z]+", t))


# --- near match ------------------------------------------------------------------------------
def _trim(blocks: list) -> list:
    while len(blocks) > 1 and blocks[0].size < 3 and blocks[1].a - (blocks[0].a + blocks[0].size) >= 2:
        blocks = blocks[1:]
    while len(blocks) > 1 and blocks[-1].size < 3 and blocks[-1].a - (blocks[-2].a + blocks[-2].size) >= 2:
        blocks = blocks[:-1]
    return blocks


def near_match(qkey: str, pkey: str) -> tuple[float, int, int]:
    """Best similarity of qkey to any window of pkey, with the window's [start, end) in pkey."""
    n = len(qkey)
    slack = max(4, n // 4)
    step = max(1, (n - 4) // 8)
    starts: set[int] = set()
    for off in range(0, max(1, n - 3), step):
        gram = qkey[off:off + 4]
        j = pkey.find(gram)
        while j != -1 and len(starts) < 80:
            starts.add(max(0, j - off))
            j = pkey.find(gram, j + 1)
    best = (0.0, 0, 0)
    for st in sorted(starts):
        ws, we = max(0, st - slack), min(len(pkey), st + n + slack)
        blocks = [b for b in SequenceMatcher(None, pkey[ws:we], qkey, autojunk=False).get_matching_blocks() if b.size]
        blocks = _trim(blocks)
        if not blocks:
            continue
        matched = sum(b.size for b in blocks)
        s, e = blocks[0].a, blocks[-1].a + blocks[-1].size
        ratio = 2 * matched / (n + (e - s))
        if ratio > best[0]:
            best = (ratio, ws + s, ws + e)
    return best


def differences(page_key: str, quote_key: str) -> list[list[str]]:
    """[page piece, quote piece] for every non-equal stretch (compared in key form)."""
    ops = SequenceMatcher(None, page_key, quote_key, autojunk=False).get_opcodes()
    return [[page_key[i1:i2], quote_key[j1:j2]] for tag, i1, i2, j1, j2 in ops if tag != "equal"]


# --- read log --------------------------------------------------------------------------------
def seen_pages(read_results: list[dict]) -> dict[str, str]:
    """page_id -> text the model was shown, from every read_pages result of this conversation.
    Ids listed under not_found / not_citable were never shown, so they are not included."""
    seen: dict[str, str] = {}
    for result in read_results:
        for page in result.get("pages", []):
            seen.setdefault(page["page_id"], "\n".join(page["paragraphs"]))
    return seen


# --- verification ----------------------------------------------------------------------------
class _Context:
    def __init__(self, corpus, read_results):
        self.corpus = corpus
        self.seen = seen_pages(read_results)
        self.keys = {pid: keyed(text) for pid, text in self.seen.items()}
        self.order = list(corpus.pages)
        self.index = {pid: i for i, pid in enumerate(self.order)}

    def label(self, page_ids: list[str]) -> str:
        first = self.corpus.label(self.corpus.pages[page_ids[0]])
        if len(page_ids) == 1:
            return first
        return f"{first} ~ {self.corpus.pages[page_ids[-1]]['printed_page']}쪽"  # 쪽

    def neighbours(self, pid: str) -> list[tuple[str, str]]:
        """Adjacent read pages of the same year, as (first, second) in reading order."""
        i = self.index.get(pid)
        pairs = []
        for a, b in ((i - 1, i), (i, i + 1)) if i is not None else ():
            if 0 <= a and b < len(self.order):
                pa, pb = self.order[a], self.order[b]
                if pa in self.seen and pb in self.seen and \
                        self.corpus.pages[pa]["year"] == self.corpus.pages[pb]["year"]:
                    pairs.append((pa, pb))
        return pairs


def _span(keyed_text: tuple[str, str, list[int]], start: int, end: int) -> str:
    disp, _, pos = keyed_text
    return disp[pos[start]:pos[end - 1] + 1]


def _check(cit: dict, sentence: str, ctx: _Context, accept_near: bool, fix_wrong_page: bool) -> dict:
    pid = str(cit.get("page_id") or "")
    quote = cit.get("quote")
    pages = ctx.corpus.pages
    r = {"page_id": pid, "quote": quote,
         "id_status": "read" if pid in ctx.seen else ("not_read" if pid in pages else "unknown"),
         "quote_status": None, "similarity": None, "evidence": None, "evidence_page_ids": [],
         "label": None, "found_on": None, "corrected": False, "missing_anchors": [], "differences": [],
         "grade": "unsupported", "valid": False}
    if pid in pages:
        r["label"] = ctx.label([pid])

    def accept(grade: str, page_ids: list[str], evidence: str) -> dict:
        r.update(grade=grade, valid=True, evidence=evidence, evidence_page_ids=page_ids, label=ctx.label(page_ids))
        return r

    if quote is None:                                   # inline marker: no quote to check
        r["quote_status"] = "none"
        if r["id_status"] != "read":
            return r
        text = ctx.seen[pid]
        r["missing_anchors"] = sorted((anchors(sentence) - anchors(text)).elements())
        want = Counter(bigram_tokens(sentence))
        lines = [ln for ln in text.split("\n") if ln.strip()] or [text]
        best = max(lines, key=lambda ln: sum((want & Counter(bigram_tokens(ln))).values()))
        return accept("page_only", [pid], normalize(best))

    qkey = cite_key(quote)
    if len(qkey) < MIN_QUOTE_KEY:
        r["quote_status"] = "too_short"
        return r

    if r["id_status"] == "read":
        k = ctx.keys[pid]
        j = k[1].find(qkey)
        if j >= 0:
            r["quote_status"] = "exact"
            return accept("verified", [pid], _span(k, j, j + len(qkey)))
        for a, b in ctx.neighbours(pid):                # quote runs over the page break
            kj = keyed(ctx.seen[a] + "\n" + ctx.seen[b])
            j = kj[1].find(qkey)
            boundary = len(ctx.keys[a][1])
            if j >= 0 and j < boundary < j + len(qkey):
                r["quote_status"] = "joined"
                return accept("verified", [a, b], _span(kj, j, j + len(qkey)))

    for other, k in ctx.keys.items():                   # quote is verbatim on another read page
        if other != pid and (j := k[1].find(qkey)) >= 0:
            r["found_on"] = other
            if fix_wrong_page:
                r["corrected"] = True
                r["quote_status"] = "exact_on_other_page"
                return accept("verified", [other], _span(k, j, j + len(qkey)))
            break

    if r["id_status"] == "read":
        k = ctx.keys[pid]
        ratio, s, e = near_match(qkey, k[1])
        r["similarity"] = round(ratio, 3)
        if ratio >= NEAR_RATIO:
            evidence = _span(k, s, e)
            r["differences"] = differences(k[1][s:e], qkey)
            changed = sum(max(len(a), len(b)) for a, b in r["differences"])
            if anchors(evidence) == anchors(quote) and changed <= NEAR_MAX_CHANGED:
                r["quote_status"] = "near"
                if accept_near:
                    return accept("near", [pid], evidence)
                r["evidence"] = evidence
                return r
            r["quote_status"] = "not_found"
            r["evidence"] = evidence
            r["missing_anchors"] = sorted((anchors(quote) - anchors(evidence)).elements())
            return r
    r["quote_status"] = "not_found" if r["id_status"] == "read" else "page_rejected"
    return r


def verify_answer(answer: dict, corpus, read_results: list[dict], *,
                  accept_near: bool = True, fix_wrong_page: bool = True) -> dict:
    """Per-sentence verdicts, badges and a numbered reference list for the UI."""
    ctx = _Context(corpus, read_results)
    references: list[dict] = []
    ref_index: dict[tuple, int] = {}
    out_sentences = []
    for i, sentence in enumerate(answer.get("sentences", [])):
        text = sentence.get("text", "")
        seen_cits, checks = set(), []
        for cit in sentence.get("citations", []):
            ident = (cit.get("page_id"), cit.get("quote"))
            if ident in seen_cits:
                continue
            seen_cits.add(ident)
            checks.append(_check(cit, text, ctx, accept_near, fix_wrong_page))
        grade = max((c["grade"] for c in checks if c["valid"]), key=GRADE_RANK.get, default="unsupported")
        numbers = []
        for c in checks:
            if not c["valid"]:
                continue
            key = (tuple(c["evidence_page_ids"]), c["evidence"])
            if key not in ref_index:
                ref_index[key] = len(references) + 1
                references.append({"n": ref_index[key], "page_ids": c["evidence_page_ids"], "label": c["label"],
                                   "evidence": c["evidence"], "grade": c["grade"]})
            if ref_index[key] not in numbers:
                numbers.append(ref_index[key])
        out_sentences.append({"index": i, "text": text, "grade": grade, "badge": BADGES[grade],
                              "refs": numbers, "citations": checks})
    return {"status": answer.get("status"), "sentences": out_sentences, "references": references,
            "counts": dict(Counter(s["grade"] for s in out_sentences)),
            "read_page_ids": list(ctx.seen)}


# --- inline markers (designs a / c) -----------------------------------------------------------
_MARKER = re.compile(re.escape(CITE_START) + "cite" + re.escape(CITE_DELIM) + "(.*?)" + re.escape(CITE_STOP), re.S)
_SOURCE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_LINE_LOCATOR = re.compile(r"^L\d+(?:-L\d+)?$")
_SENTENCE_END = re.compile(r"(?<=[.!?\u3002])\s+")


def parse_inline_answer(text: str, status: str | None = "answered") -> dict:
    """Turn prose with OpenAI-style markers into the answer dict (quote=None).
    A marker belongs to the sentence written just before it."""
    sentences: list[dict] = []
    open_sentence = False
    pos = 0
    matches = list(_MARKER.finditer(text))
    for m in matches + [None]:
        chunk = text[pos:m.start() if m else len(text)]
        parts = _SENTENCE_END.split(chunk)
        for n, part in enumerate(parts):
            if not part.strip():
                continue
            if n == 0 and open_sentence and sentences:      # marker was inside a long sentence
                glue = " " if part[:1].isspace() else ""
                sentences[-1]["text"] += glue + part.strip()
            else:
                sentences.append({"text": part.strip(), "citations": []})
        if chunk.strip():
            open_sentence = not re.search(r"[.!?\u3002]\s*$", chunk)
        if m is None:
            break
        ids = [p.strip() for p in m.group(1).split(CITE_DELIM) if p.strip()]
        ids = [p for p in ids if _SOURCE_ID.match(p) and not _LINE_LOCATOR.match(p)]
        if sentences:
            sentences[-1]["citations"].extend({"page_id": p, "quote": None} for p in ids)
        pos = m.end()
    return {"sentences": sentences, "status": status}


def schema_problems(schema: dict, path: str = "$") -> list[str]:
    """Strict-mode rules from the Structured Outputs guide: every object sets
    additionalProperties false and lists every property as required."""
    problems = []
    if schema.get("type") == "object":
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is not False:
            problems.append(f"{path}: additionalProperties must be false")
        if sorted(schema.get("required", [])) != sorted(props):
            problems.append(f"{path}: required must list every property")
        for name, sub in props.items():
            problems += schema_problems(sub, f"{path}.{name}")
    if schema.get("type") == "array":
        problems += schema_problems(schema.get("items", {}), f"{path}[]")
    return problems


if __name__ == "__main__":   # demo: python citation_check.py  (cwd = project root)
    import json
    import sys
    from pathlib import Path

    from assistant.corpus import Corpus

    corpus = Corpus(Path("corpus"))
    reads = [corpus.read_pages(["2021-p112L", "2021-p112R", "2021-p134R"])]
    demo = {"status": "answered", "sentences": [
        {"text": "국립외교원은 2021년 제8회 외교관후보자 정규과정을 약 46주 동안 운영했습니다.",
         "citations": [{"page_id": "2021-p112R", "quote": "2021년 \u2018제8회 외교관후보자 정규과정\u2019을 약 46주 동안 운영했다"}]},
        {"text": "교육생은 모두 47명이었습니다.",
         "citations": [{"page_id": "2021-p112L", "quote": "교육생 총 47명(일반 외교 44명, 지역 외교 3명)"}]},
        {"text": "한\u00b7미\u00b7일 3자 회의는 제10차였습니다.",
         "citations": [{"page_id": "2021-p134R", "quote": "제10차 한미일(KNDA CEIP JIIA) 3자 회의"}]},
        {"text": "이 회의는 서울에서 열렸습니다.", "citations": [{"page_id": "2021-p999L", "quote": "3자 회의 (서울)"}]},
        {"text": "자세한 내용은 아래 근거를 보세요.", "citations": []},
    ]}
    json.dump(verify_answer(demo, corpus, reads), sys.stdout, ensure_ascii=False, indent=1)
    print()
