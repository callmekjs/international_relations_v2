"""Per-printed-page text extraction for the six 2020-2025 Korean diplomatic white papers.

Public API
    extract_half_text(pdf_path, pdf_page, side) -> str
        Text of one half ('L' or 'R') of a two-page-spread PDF page, in reading order.
        Lossless: every non-whitespace character inside the half appears exactly once.
        Layout of the returned string (blocks separated by one blank line):
            [running-header block]   header-band lines (page number, chapter/section title)
            [body paragraphs ...]    one visual line per line, trailing spaces kept,
                                     a blank line at every paragraph / block boundary
            [footer block]           footer-band lines (page numbers in 2020 and 2025)
            [margin block]           side-tab text in the outer margin
    clean_text(text, volume_year) -> str
        Drops running header / footer / side-tab blocks, joins the visual lines of each
        paragraph (trailing-space rule), normalises characters and whitespace.
        One paragraph (or table cell / heading) per output line.
        Needs running_strings.json (built once by build_running_strings) next to this file.
    find_image_only(pdf_path) -> list[tuple[int, str]]
        Halves with <= 20 body characters but visible image / vector content.

Helpers: extract_half_lines (lines + role), normalize_text (clean without stripping),
classify_half (text | image_only | blank | little_text), build_running_strings.

pdf_page is 1-based. Requires PyMuPDF (tested with 1.26.7).
"""
from __future__ import annotations

import collections
import functools
import json
import os
import re

import pymupdf as fitz

fitz.TOOLS.mupdf_display_errors(False)

# ligatures + whitespace preserved, mediabox clip, CID for unknown unicode; no images
TEXT_FLAGS = fitz.TEXTFLAGS_TEXT

MARGIN_W = 50.0          # outer-margin strip (pt) holding side tabs
BAND_TOL = 3.5           # |y0 - band_y| tolerance (pt) for header / footer bands
MIN_BAND_SHARE = 0.25    # a band must be used on >= 25 % of spread pages
IMAGE_ONLY_MAX_CHARS = 20

HANGUL = "가-힣"
LIST_MARKER = re.compile(
    r"^\s*(?:[•·∙\-–—○●◦□■◆◇▶▷►▴▪※*ㅇ]|[①-⑳]|\(?\d{1,2}\)|\d{1,2}\.\s|<|〈|\[|제\s?\d{1,2}\s?[장절])"
)
SENT_END = re.compile(r"[.!?。][\"'’”)\]」』]*$")


# --------------------------------------------------------------------------- helpers
@functools.lru_cache(maxsize=8)
def _doc(pdf_path: str) -> fitz.Document:
    return fitz.open(pdf_path)


def _is_spread(page: fitz.Page) -> bool:
    return page.rect.width > page.rect.height * 1.2


def half_rect(page: fitz.Page, side: str):
    """Clip rectangle of a half. Non-spread (single) pages: 'L' = whole page, 'R' = None."""
    r = page.rect
    if side not in ("L", "R"):
        raise ValueError("side must be 'L' or 'R'")
    if not _is_spread(page):
        return fitz.Rect(r) if side == "L" else None
    mid = r.x0 + r.width / 2
    return fitz.Rect(r.x0, r.y0, mid, r.y1) if side == "L" else fitz.Rect(mid, r.y0, r.x1, r.y1)


GAP_EM = 0.5   # horizontal gap (in em) between two non-space glyphs that becomes a space


def _line_text(line: dict) -> str:
    """Line text from rawdict glyphs. MuPDF sometimes merges neighbouring table cells or a
    '제1절' label and its title into one line without a space ('면담한-CARICOM',
    '제1절북한'); a glyph gap wider than GAP_EM x font size is turned into a space.
    Measured on all six volumes: such gaps occur in < 20 lines per volume and body text
    never has them."""
    out = []
    prev = None
    for s in line["spans"]:
        for c in s["chars"]:
            ch = c["c"]
            if prev is not None and not ch.isspace() and not prev["c"].isspace():
                if c["bbox"][0] - prev["bbox"][2] > GAP_EM * s["size"]:
                    out.append(" ")
            out.append(ch)
            prev = c
    return "".join(out).replace("\n", " ").replace("\r", " ")


def _span_text(span: dict) -> str:
    return "".join(c["c"] for c in span["chars"])


def _main_span(line: dict) -> dict:
    return max(line["spans"], key=lambda s: len(_span_text(s).strip()))


@functools.lru_cache(maxsize=8)
def _profile(pdf_path: str) -> dict:
    """Learn running header / footer y-bands of one volume from repeated lines.

    A band is the most common rounded y0 of short lines in the top 12 % (header) or of
    page-number lines in the bottom 15 % (footer), kept only when it occurs on
    >= MIN_BAND_SHARE of the spread pages.
    """
    doc = _doc(pdf_path)
    top, bot = collections.Counter(), collections.Counter()
    n = 0
    for page in doc:
        if not _is_spread(page):
            continue
        n += 1
        H = page.rect.height
        lines = collections.defaultdict(list)
        for w in page.get_text("words", flags=TEXT_FLAGS):
            lines[(w[5], w[6])].append(w)
        tseen, bseen = set(), set()
        for ws in lines.values():
            y0 = min(w[1] for w in ws)
            y1 = max(w[3] for w in ws)
            txt = " ".join(w[4] for w in ws)
            if y1 < 0.12 * H:
                tseen.add(round(y0))
            elif y0 > 0.85 * H and re.fullmatch(r"\d{1,3}", txt.strip()):
                bseen.add(round(y0))
        top.update(tseen)
        bot.update(bseen)

    def band(counter):
        if not counter or not n:
            return None
        y, c = counter.most_common(1)[0]
        if c < MIN_BAND_SHARE * n:
            return None
        # weighted centre of the cluster around the mode
        near = {k: v for k, v in counter.items() if abs(k - y) <= BAND_TOL}
        return sum(k * v for k, v in near.items()) / sum(near.values())

    return {"header_y": band(top), "footer_y": band(bot), "spread_pages": n}


def _merge_vertical(lines: list[dict]) -> list[dict]:
    """Merge runs of one-glyph vertical lines (org charts) into one vertical line."""
    out: list[dict] = []
    for ln in lines:
        prev = out[-1] if out else None
        if (
            prev is not None
            and prev["vertical"]
            # next vertical glyph, or an upright 1-2 character piece (e.g. the '2' in 아태2과)
            and (ln["vertical"] or len(ln["text"].strip()) <= 2)
            and abs((prev["bbox"][0] + prev["bbox"][2]) - (ln["bbox"][0] + ln["bbox"][2])) / 2 < 0.6 * prev["size"]
            and -0.5 * ln["size"] <= ln["bbox"][1] - prev["bbox"][3] < ln["size"]
        ):
            prev["text"] = prev["text"].rstrip() + ln["text"]
            prev["bbox"] = (prev["bbox"][0], prev["bbox"][1], max(prev["bbox"][2], ln["bbox"][2]), ln["bbox"][3])
            continue
        out.append(dict(ln))
    return out


def extract_half_lines(pdf_path: str, pdf_page: int, side: str) -> list[dict]:
    """Lines of one half in MuPDF (content-stream) order, each tagged with a role:
    'header' | 'footer' | 'margin' | 'body'."""
    doc = _doc(pdf_path)
    page = doc[pdf_page - 1]
    clip = half_rect(page, side)
    if clip is None:
        return []
    prof = _profile(pdf_path)
    H = page.rect.height
    spread = _is_spread(page)
    d = page.get_text("rawdict", clip=clip, flags=TEXT_FLAGS)
    lines = []
    for bi, b in enumerate(d["blocks"]):
        if b.get("type", 0) != 0:
            continue
        for li, l in enumerate(b["lines"]):
            t = _line_text(l)
            if not t.strip():
                continue
            ms = _main_span(l)
            lines.append(
                dict(
                    text=t,
                    bbox=tuple(l["bbox"]),
                    size=round(ms["size"], 2),
                    font=ms["font"],
                    base=ms["origin"][1],       # baseline; line bboxes can be inflated by tall glyphs
                    vertical=abs(l["dir"][0]) < 0.99,
                    block=bi,
                    line=li,
                )
            )
    lines = _merge_vertical(lines)
    for ln in lines:
        x0, y0, x1, y1 = ln["bbox"]
        role = "body"
        if spread and prof["header_y"] is not None and y1 < 0.12 * H and abs(y0 - prof["header_y"]) <= BAND_TOL:
            role = "header"
        elif spread and prof["footer_y"] is not None and y0 > 0.85 * H and abs(y0 - prof["footer_y"]) <= BAND_TOL:
            role = "footer"
        elif spread and ((side == "R" and x0 >= clip.x1 - MARGIN_W) or (side == "L" and x1 <= clip.x0 + MARGIN_W)):
            role = "margin"
        ln["role"] = role
    return lines


def _reorder_body(body: list[dict], H: float) -> list[dict]:
    """Keep MuPDF (content-stream) order, with two targeted fixes:
    1. display titles (>= body size + 2 pt) lying above the first body-size line are moved
       up to just before the first line below them, ordered by row then x
       (e.g. '제1절' before '신남방정책 고도화', '국제정세 개관' before '1. 개관')
    2. footnote zone (small type from the first '1)' marker down, with no body-size text
       below it) -> end, ordered by y then x
    Not used: sort=True. For "text" it re-synthesises lines from words with layout
    padding (interleaves table cells); for "dict" it sorts blocks by (y1, x0).
    """
    if not body:
        return body
    chars = collections.Counter()
    for ln in body:
        chars[ln["size"]] += len(ln["text"].strip())
    dom = chars.most_common(1)[0][0]
    body_lines = [ln for ln in body if abs(ln["size"] - dom) <= 0.6 and not ln["vertical"]]
    top_body = min((ln["bbox"][1] for ln in body_lines), default=None)
    bottom_body = max((ln["bbox"][1] for ln in body_lines), default=None)

    # 2. footnote zone
    feet: list[dict] = []
    if bottom_body is not None:
        markers = [
            ln for ln in body
            if not ln["vertical"] and ln["size"] <= dom - 1.0 and ln["bbox"][1] > max(bottom_body, 0.55 * H)
            and re.match(r"^\d{1,2}\)", ln["text"].replace("\x07", "").strip())
        ]
        if markers:
            fy = min(ln["bbox"][1] for ln in markers)
            feet = [ln for ln in body if not ln["vertical"] and ln["size"] <= dom - 1.0 and ln["bbox"][1] >= fy - 0.5]
    fid = {id(l) for l in feet}

    # 1. display titles (>= body size + 2 pt) lying above the first body-size line: each is
    #    inserted just before the first other line that sits below it, titles sharing an
    #    insertion point are ordered by row then x
    titles: list[dict] = []
    if top_body is not None:
        titles = [
            l for l in body
            if id(l) not in fid and not l["vertical"] and l["size"] >= dom + 2 and l["bbox"][3] <= top_body + 1
        ]
    tid = {id(l) for l in titles}
    rest = [l for l in body if id(l) not in fid and id(l) not in tid]

    def row_key(l):
        return (round(l["bbox"][1] / 8), l["bbox"][0])

    slots: dict[int, list[dict]] = collections.defaultdict(list)
    for t in titles:
        pos = next((i for i, n in enumerate(rest) if n["bbox"][1] >= t["bbox"][3] - 1), len(rest))
        slots[pos].append(t)
    ordered: list[dict] = []
    for i in range(len(rest) + 1):
        ordered.extend(sorted(slots.get(i, []), key=row_key))
        if i < len(rest):
            ordered.append(rest[i])
    feet_sorted = sorted(feet, key=lambda l: (l["bbox"][1], l["bbox"][0]))
    return ordered + feet_sorted


def _aligned(x: dict, y: dict) -> bool:
    """Two lines of one justified column: same left edge (+-1.5 em) and right edge (+-3.5 pt)."""
    return abs(x["bbox"][2] - y["bbox"][2]) <= 3.5 and abs(x["bbox"][0] - y["bbox"][0]) <= 1.5 * x["size"]


def _continues(a: dict, b: dict, col_right: float, a_prev: dict | None = None) -> bool:
    """Is visual line b the continuation of line a within the same paragraph?
    a_prev = the line before a when it belongs to a's paragraph (for narrow columns)."""
    if a["vertical"] or b["vertical"]:
        return False
    if abs(a["size"] - b["size"]) > 0.3 or a["font"] != b["font"]:
        return False
    ax0, ay0, ax1, ay1 = a["bbox"]
    bx0, by0, bx1, by1 = b["bbox"]
    size = a["size"]
    if not (0.9 * size <= b["base"] - a["base"] <= 2.4 * size):   # next line (pitch 1.6-2.0 em)
        return False
    if min(ax1, bx1) - max(ax0, bx0) <= 0:          # same column
        return False
    if LIST_MARKER.match(b["text"].replace("\x07", "")):
        return False
    at = a["text"]
    # a soft line break only happens when line a is filled to the column's right edge;
    # the width floor keeps stacked short table cells ("38" / "35" / "54") apart
    # (text wrapped beside a photo is narrower: a line aligned with the next line, or with
    #  the previous line of its own paragraph, also counts as filling its column)
    wide = (ax1 - ax0) >= 8 * size
    full = wide and (
        ax1 >= col_right - 1.2 * size
        or _aligned(a, b)
        or (a_prev is not None and a_prev["font"] == a["font"] and _aligned(a_prev, a))
    )
    if not full:
        return False
    if at[-1:].isspace():
        return True
    # no trailing space: mid-word break, unless a ends a sentence (= paragraph end)
    return not SENT_END.search(at.rstrip())


def _col_right(ln: dict, lines: list[dict]) -> float:
    """Right edge of the text column of line ln: widest same-size line in the half that
    overlaps ln horizontally and starts within 40 pt of it."""
    x0, _, x1, _ = ln["bbox"]
    best = x1
    for o in lines:
        if o["vertical"] or abs(o["size"] - ln["size"]) > 0.3:
            continue
        ox0, _, ox1, _ = o["bbox"]
        if min(x1, ox1) - max(x0, ox0) > 0 and abs(ox0 - x0) < 40:
            best = max(best, ox1)
    return best


def _rows(lines: list[dict]) -> list[str]:
    """Group band lines into rows (same y) and join each row left to right."""
    rows: list[list[dict]] = []
    for ln in sorted(lines, key=lambda l: (l["bbox"][1], l["bbox"][0])):
        if rows and abs(rows[-1][0]["bbox"][1] - ln["bbox"][1]) < 4:
            rows[-1].append(ln)
        else:
            rows.append([ln])
    return [" ".join(l["text"].strip() for l in sorted(r, key=lambda l: l["bbox"][0])) for r in rows]


def extract_half_text(pdf_path: str, pdf_page: int, side: str, *, running: bool = True) -> str:
    """See module docstring. running=False omits the header / footer / margin blocks."""
    lines = extract_half_lines(pdf_path, pdf_page, side)
    if not lines:
        return ""
    H = _doc(pdf_path)[pdf_page - 1].rect.height
    header = [l for l in lines if l["role"] == "header"]
    footer = [l for l in lines if l["role"] == "footer"]
    margin = [l for l in lines if l["role"] == "margin"]
    body = _reorder_body([l for l in lines if l["role"] == "body"], H)

    parts: list[str] = []
    if header and running:
        parts.append("\n".join(_rows(header)))
    paras: list[list[str]] = []
    prev = prev_prev = None
    for ln in body:
        if prev is not None and _continues(prev, ln, _col_right(prev, body), prev_prev):
            paras[-1].append(ln["text"])
            prev_prev = prev
        else:
            paras.append([ln["text"]])
            prev_prev = None
        prev = ln
    parts.extend("\n".join(p) for p in paras)
    if footer and running:
        parts.append("\n".join(_rows(footer)))
    if margin and running:
        parts.append("\n".join(l["text"].strip() for l in margin))
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- cleaning
_RUNNING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "running_strings.json")


def _mask(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d", "#", s.replace("\x07", "").replace("\x08", ""))).strip()


@functools.lru_cache(maxsize=1)
def _running() -> dict:
    try:
        with open(_RUNNING_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {int(y): {k: set(v) for k, v in d.items()} for y, d in data.items()}
    except (OSError, ValueError):
        return {}


_FALLBACK_HEADER = re.compile(r"^(#{1,3}|제\s?#{1,2}\s?[장절].*|부록\.?|.{0,40}현황|#### ?년 .{0,10}일지)$")
_PAGE_NO = re.compile(r"^#{1,3}$")


def build_running_strings(pdf_paths: dict[int, str]) -> dict:
    """Collect masked header / footer / margin strings per year from geometric roles."""
    out = {}
    for year, path in pdf_paths.items():
        sets = {"header": set(), "footer": set(), "margin": set()}
        for p in range(1, _doc(path).page_count + 1):
            for side in "LR":
                lines = extract_half_lines(path, p, side)
                for role in ("header", "footer"):
                    for row in _rows([l for l in lines if l["role"] == role]):
                        sets[role].add(_mask(row))
                for l in lines:
                    if l["role"] == "margin":
                        sets["margin"].add(_mask(l["text"]))
        out[year] = {k: sorted(v) for k, v in sets.items()}
    with open(_RUNNING_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    _running.cache_clear()
    return out


def _block_is(block_lines: list[str], year: int, kinds: tuple[str, ...]) -> bool:
    """True when every line of the block is a known running string of this volume
    (learned from geometry, digits masked). Without the learned file: header = regex,
    footer = bare page number."""
    known = _running().get(year)
    seen = False
    for raw in block_lines:
        m = _mask(raw)
        if not m:
            continue
        seen = True
        if known is not None:
            if not any(m in known[k] for k in kinds):
                return False
        elif "header" in kinds:
            if not _FALLBACK_HEADER.match(m):
                return False
        elif not _PAGE_NO.match(m):
            return False
    return seen


_CHAR_MAP = str.maketrans(
    {
        "ㆍ": "·",  # HANGUL LETTER ARAEA used as middle dot (2021)
        "･": "·",  # HALFWIDTH KATAKANA MIDDLE DOT (2025)
        "‧": "·",  # HYPHENATION POINT (2023)
        "・": "·",
        "": "·",  # private-use glyph between two nouns (2025 p.43)
        "｢": "「",
        "｣": "」",
        " ": " ",
        "　": " ",
        "\t": " ",
        "\x07": "",     # InDesign 'indent to here'
        "\x08": "",
        "​": "",
        "‌": "",
        "‍": "",
        "﻿": "",
    }
)


def _join_lines(lines: list[str]) -> str:
    out = ""
    for i, ln in enumerate(lines):
        if i == 0:
            out = ln
            continue
        prev = out
        if prev.endswith("\u00ad"):                        # InDesign auto-hyphenation (2023, 2024)
            out = prev[:-1] + ln.lstrip()
        # a hard '-' at line end is always a real hyphen in these volumes (Al-/Safadi,
        # Chan-/o-cha, Asia-/Pacific): falls through to the no-space join below
        elif prev[-1:].isspace():
            out = prev.rstrip() + " " + ln.lstrip()
        elif SENT_END.search(prev.rstrip()):
            out = prev + "\n" + ln                          # paragraph end missed by geometry
        else:
            out = prev + ln.lstrip()                        # mid-word break
    return out


def _blocks(text: str) -> list[list[str]]:
    return [b.split("\n") for b in re.split(r"\n[ \t]*\n", text) if b.strip()]


def clean_text(text: str, volume_year: int) -> str:
    """Strip the running blocks that extract_half_text puts first (header) and last
    (footer, then side tab), then normalise (see normalize_text).

    A block is stripped only if every line is a known running string of that volume
    (running_strings.json, digits masked) AND the volume's co-occurrence pattern holds
    (verified on all halves of the six volumes):
      * footer / side tab never occur without a header -> strip them only after a header;
      * 2020, 2025 (page number in the footer): header and footer always come together;
      * 2021-2024 (page number in the header): the header row always contains a number.
    This keeps chapter-opener titles such as '부록' or '지역 외교' that equal a running string.
    """
    blocks = _blocks(text)
    known = _running().get(volume_year)
    if not blocks or not _block_is(blocks[0], volume_year, ("header",)):
        return _normalize(blocks)
    body = blocks[1:]
    if body and _block_is(body[-1], volume_year, ("margin",)):
        body = body[:-1]
    if known is not None and known["footer"]:
        if body and _block_is(body[-1], volume_year, ("footer",)):
            body = body[:-1]
        else:
            return _normalize(blocks)          # no footer -> the 'header' was body text
    elif known is not None and not any(re.search(r"(^|\s)#{1,3}(\s|$)", l) for l in map(_mask, blocks[0])):
        return _normalize(blocks)              # header without its page number -> body text
    return _normalize(body)


def normalize_text(text: str) -> str:
    """Line joining + character / whitespace normalisation only (no block stripping)."""
    return _normalize(_blocks(text))


def _normalize(blocks: list[list[str]]) -> str:
    paras = []
    for b in blocks:
        s = _join_lines(b).translate(_CHAR_MAP)
        s = s.replace("\u00ad", "")
        for p in s.split("\n"):
            p = re.sub(r"^\s*∙", "• ", p)
            p = p.replace("∙", "·")
            p = re.sub(r"[ ]{2,}", " ", p).strip()
            if re.fullmatch(r"(?:[가-힣] ){1,4}[가-힣]", p):   # letter-spaced label: '양 자 관 계'
                p = p.replace(" ", "")
            if p:
                paras.append(p)
    return "\n".join(paras)


# --------------------------------------------------------------------------- image-only
INK_ZOOM, INK_TOL = 0.5, 25   # render scale and grey-level distance from the background
INK_BLANK = 0.002             # < 0.2 % non-background pixels = visually empty
INK_DENSE = 0.06              # >= 6 % = dense content (greeting letter, TOC, org chart)


def _ink_ratio(page: fitz.Page, clip: fitz.Rect) -> float:
    pix = page.get_pixmap(matrix=fitz.Matrix(INK_ZOOM, INK_ZOOM), clip=clip, colorspace=fitz.csGRAY, alpha=False)
    hist = collections.Counter(pix.samples)
    mode = hist.most_common(1)[0][0]
    return sum(c for v, c in hist.items() if abs(v - mode) > INK_TOL) / max(1, len(pix.samples))


def classify_half(pdf_path: str, pdf_page: int, side: str) -> dict:
    """kind: 'text' | 'image_only' | 'blank' | 'little_text' | 'no_half'.
    image_only = <= IMAGE_ONLY_MAX_CHARS body characters, visible ink, and an image
    (>= 30 % of the half) or >= 200 vector path items; density 'dense' | 'sparse'."""
    page = _doc(pdf_path)[pdf_page - 1]
    clip = half_rect(page, side)
    if clip is None:
        return {"kind": "no_half"}
    body = [l for l in extract_half_lines(pdf_path, pdf_page, side) if l["role"] == "body"]
    n = sum(len(re.sub(r"\s", "", l["text"])) for l in body)
    info = {"kind": "text", "body_chars": n}
    if n > IMAGE_ONLY_MAX_CHARS:
        return info
    area = 0.0
    for im in page.get_image_info():
        r = fitz.Rect(im["bbox"]) & clip
        if not r.is_empty:
            area += r.width * r.height
    cover = min(1.0, area / (clip.width * clip.height))
    items = sum(len(d["items"]) for d in page.get_drawings() if fitz.Rect(d["rect"]).intersects(clip))
    ink = _ink_ratio(page, clip)
    info.update(image_cover=round(cover, 3), vector_items=items, ink=round(ink, 4))
    if ink >= INK_BLANK and (cover >= 0.3 or items >= 200):
        info["kind"] = "image_only"
        info["density"] = "dense" if ink >= INK_DENSE else "sparse"
    elif n == 0:
        info["kind"] = "blank"
    else:
        info["kind"] = "little_text"
    return info


def find_image_only(pdf_path: str) -> list[tuple[int, str]]:
    """Halves whose body (header / footer / side tab excluded) has <= IMAGE_ONLY_MAX_CHARS
    characters but visible image / vector content (see classify_half). Single pages: 'L' only."""
    doc = _doc(pdf_path)
    out = []
    for p in range(1, doc.page_count + 1):
        for side in ("LR" if _is_spread(doc[p - 1]) else "L"):
            if classify_half(pdf_path, p, side)["kind"] == "image_only":
                out.append((p, side))
    return out
