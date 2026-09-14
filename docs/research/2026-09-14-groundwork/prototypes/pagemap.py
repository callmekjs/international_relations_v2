"""Printed-page mapping for the six two-page-spread white paper PDFs (data folders 2020-2025).

Public API
    map_pages(pdf_path, policy="k") -> list[dict]      one dict per printed-page slot, reading order
        pdf_page        int      1-based PDF page number (PyMuPDF index = pdf_page - 1)
        side            'L'|'R'  half of the spread; a single-width page is one slot, side 'L' unless its
                                 folio says it is the right-hand number (2N+k+1)
        clip            (x0, y0, x1, y1) in PyMuPDF page coordinates (page.rect, top-left origin);
                                 use page.get_text(..., clip=clip) (no shared textpage) or slot_text(page, clip)
        printed_page    int|None
        page_label      str      str(printed_page), or "PDF<N><side>" when printed_page is None
        label_source    'detected'  a folio was read on this slot and equals printed_page
                        'k'         printed_page = 2N+k+(side=='R') without an agreeing folio
                                    (no folio printed, or the folio disagrees -> see detected_number)
                        'none'      no printed page (2N+k < 1, e.g. the cover spread)
        extra keys: detected_number (int|None), k_page (int), agrees (bool|None), n_words (int)
    analyze(pdf_path) -> dict    k, votes, match rate, disagreements, offset runs, no-folio slots, printed range
    verify_split(pdf_path) -> dict   word- and character-multiset comparison, full page vs L+R (two methods)
    slot_text(page, clip) -> str     slot text from full-page lines (recommended over get_text(clip=...))

Model (verified on the six volumes, see notes.md)
    PDF page N (1-based) holds printed pages 2N+k (left half) and 2N+k+1 (right half).
    Equivalent 0-based form: index i = N-1 holds 2i+k+2 and 2i+k+3.

policy
    "k"         printed_page always follows 2N+k (unique, gap-free, matches the books' own tables of contents)
    "detected"  a folio read on the slot wins over 2N+k; a k-derived number that collides with a detected
                one elsewhere becomes None. Gives what is printed on the page, at the cost of gaps/holes.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from functools import lru_cache

import pymupdf as fitz  # PyMuPDF 1.26.7

fitz.TOOLS.mupdf_display_errors(False)

SPREAD_RATIO = 1.2      # width/height at or above this -> two-page spread
GUTTER_WINDOW = 0.15    # search the gutter inside W/2 +- 15 % of W
VOTE_BAND = 0.085       # pass 1: word centre within 8.5 % of H from the top or bottom edge
OUTER_FRACTION = 0.25   # pass 1: word lies in the outer quarter of its half
DETECT_BAND = 0.15      # pass 2: search band for words at a learned folio position
TOL_X, TOL_Y = 8.0, 5.0 # pass 2: distance to a learned folio position (points)
MIN_SUPPORT = 3         # pass 2: a folio position needs this many agreeing pass-1 votes nearby

RE_ARABIC = re.compile(r"\d{1,3}")
RE_MUPDF_DELIM = re.compile(r"[\x00-\x20\xa0\u202a-\u202e]+")  # MuPDF word delimiters: code <= 32, NBSP, bidi marks
RE_ROMAN = re.compile(r"(?i)(?=[ivxlc]+$)c{0,3}(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})")


# --------------------------------------------------------------------------- geometry
def _split_x(words, W: float) -> float:
    """x of the cut between left and right halves: W/2 if no word crosses it, else the nearest word-free x."""
    mid = W / 2
    lo, hi = mid - GUTTER_WINDOW * W, mid + GUTTER_WINDOW * W
    spans = sorted((w[0], w[2]) for w in words if w[2] > lo and w[0] < hi)
    gaps, cur = [], lo
    for a, b in spans:
        if a > cur:
            gaps.append((cur, a))
        cur = max(cur, b)
    if cur < hi:
        gaps.append((cur, hi))
    if not gaps:
        return mid                      # nothing free: verify_split will report the loss/duplication
    for a, b in gaps:
        if a <= mid <= b:
            return mid
    a, b = min(gaps, key=lambda g: min(abs(g[0] - mid), abs(g[1] - mid)))
    if b - a <= 1.0:
        return (a + b) / 2
    return a + 0.5 if abs(a - mid) <= abs(b - mid) else b - 0.5


def _page_slots(page):
    W, H = page.rect.width, page.rect.height
    full = page.get_text("words")
    if W / H >= SPREAD_RATIO:
        x = _split_x(full, W)
        return full, [("L", (0.0, 0.0, x, H)), ("R", (x, 0.0, W, H))]
    return full, [(None, (0.0, 0.0, W, H))]


# --------------------------------------------------------------------------- folio candidates
def _candidates(words, clip, side, H):
    """Numeric words near the top/bottom edge. dist = distance of the word's outer edge to the slot's outer edge."""
    x0c, _, x1c, _ = clip
    half_w = x1c - x0c
    out = []
    for w in words:
        text = w[4].strip()
        yc = (w[1] + w[3]) / 2
        if yc < DETECT_BAND * H:
            band, edge_dist = "T", yc
        elif yc > (1 - DETECT_BAND) * H:
            band, edge_dist = "B", H - yc
        else:
            continue
        if RE_ARABIC.fullmatch(text):
            kind, value = "arabic", int(text)
            if value == 0:
                continue
        elif RE_ROMAN.fullmatch(text):
            kind, value = "roman", _roman(text)
        else:
            continue
        sides = [side] if side else ["L", "R"]
        for s in sides:
            dist = (w[0] - x0c) if s == "L" else (x1c - w[2])
            out.append(dict(side=s, band=band, dist=dist, yc=yc, edge_dist=edge_dist, kind=kind,
                            value=value, text=text, outer=dist < OUTER_FRACTION * half_w))
    return out


def _roman(s: str) -> int:
    vals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    total, prev = 0, 0
    for ch in reversed(s.lower()):
        v = vals[ch]
        total, prev = (total - v, prev) if v < prev else (total + v, v)
    return total


# --------------------------------------------------------------------------- core scan
@lru_cache(maxsize=8)
def _scan(pdf_path: str):
    doc = fitz.open(pdf_path)
    pages = []
    try:
        for i, page in enumerate(doc):
            full, clips = _page_slots(page)
            H = page.rect.height
            slots = []
            for side, clip in clips:
                ws = page.get_text("words", clip=clip)
                slots.append(dict(side=side, clip=tuple(clip), words=ws,
                                  cands=_candidates(ws, clip, side, H)))
            pages.append(dict(N=i + 1, W=page.rect.width, H=H, full=full, slots=slots))
    finally:
        doc.close()

    # pass 1: vote k on outer-corner arabic numbers close to the page edge, spread pages only
    votes = Counter()
    for p in pages:
        if len(p["slots"]) != 2:
            continue
        for s in p["slots"]:
            for c in s["cands"]:
                if c["kind"] == "arabic" and c["outer"] and c["edge_dist"] < VOTE_BAND * p["H"]:
                    votes[c["value"] - 2 * p["N"] - (c["side"] == "R")] += 1
    if not votes:
        raise ValueError(f"no folio candidates found in {pdf_path}")
    k = votes.most_common(1)[0][0]

    # pass 2: learn folio positions from agreeing votes, then read one folio per slot at those positions
    support = []
    for p in pages:
        if len(p["slots"]) != 2:
            continue
        for s in p["slots"]:
            for c in s["cands"]:
                if (c["kind"] == "arabic" and c["outer"] and c["edge_dist"] < VOTE_BAND * p["H"]
                        and c["value"] == 2 * p["N"] + k + (c["side"] == "R")):
                    support.append((c["side"], c["band"], c["dist"], c["yc"]))

    def at_folio_position(c):
        n = sum(1 for sd, bd, dist, yc in support
                if sd == c["side"] and bd == c["band"] and abs(dist - c["dist"]) <= TOL_X
                and abs(yc - c["yc"]) <= TOL_Y)
        return n >= MIN_SUPPORT

    for p in pages:
        for s in p["slots"]:
            hits = [c for c in s["cands"] if at_folio_position(c)]
            s["folio_hits"] = hits
    return dict(pages=pages, k=k, votes=votes)


def _slot_side(p, s, k):
    if s["side"]:
        return s["side"]
    for c in s["folio_hits"]:          # single-width page: let a folio decide the side
        if c["kind"] == "arabic" and c["value"] == 2 * p["N"] + k + (c["side"] == "R"):
            return c["side"]
    return "L"


def _detected(p, s, side, k):
    hits = [c for c in s["folio_hits"] if c["side"] == side]
    if not hits:
        return None, None
    exp = 2 * p["N"] + k + (side == "R")
    hits.sort(key=lambda c: (c["kind"] != "arabic", c["value"] != exp))
    return hits[0]["value"], hits[0]["text"]


# --------------------------------------------------------------------------- public API
def map_pages(pdf_path: str, policy: str = "k") -> list[dict]:
    if policy not in ("k", "detected"):
        raise ValueError("policy must be 'k' or 'detected'")
    scan = _scan(str(pdf_path))
    k = scan["k"]
    rows = []
    for p in scan["pages"]:
        for s in p["slots"]:
            side = _slot_side(p, s, k)
            k_page = 2 * p["N"] + k + (side == "R")
            det, _ = _detected(p, s, side, k)
            agrees = None if det is None else (det == k_page)
            if policy == "detected" and det is not None:
                printed = det
            else:
                printed = k_page if k_page >= 1 else None
            rows.append(dict(pdf_page=p["N"], side=side, clip=s["clip"], printed_page=printed,
                             detected_number=det, k_page=k_page, agrees=agrees, n_words=len(s["words"])))
    if policy == "detected":
        detected_numbers = Counter(r["printed_page"] for r in rows if r["detected_number"] is not None)
        for r in rows:
            if r["detected_number"] is None and r["printed_page"] in detected_numbers:
                r["printed_page"] = None
    for r in rows:
        if r["printed_page"] is None:
            r["label_source"] = "none"
            r["page_label"] = f"PDF{r['pdf_page']}{r['side']}"
        else:
            r["label_source"] = "detected" if r["detected_number"] == r["printed_page"] else "k"
            r["page_label"] = str(r["printed_page"])
    return rows


def slot_text(page, clip, page_dict=None) -> str:
    """Text of one slot built from the FULL-page layout: every text line goes to the slot holding its centre.
    Avoids a MuPDF clip side effect seen on 3 chapter-divider pages of 2023 (a giant chapter numeral glued
    to the previous line, e.g. '기조1'). Lines never cross the cut in the six volumes (verify_split checks it).
    Pass page_dict=page.get_text("dict") to reuse one extraction for both halves."""
    d = page_dict if page_dict is not None else page.get_text("dict")
    x0, y0, x1, y1 = clip
    out = []
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        lines = [l for l in b["lines"]
                 if x0 <= (l["bbox"][0] + l["bbox"][2]) / 2 < x1 and y0 <= (l["bbox"][1] + l["bbox"][3]) / 2 <= y1]
        if lines:
            out.append("\n".join("".join(sp["text"] for sp in l["spans"]) for l in lines))
    return "\n\n".join(out)


def verify_split(pdf_path: str) -> dict:
    """Split check on every spread page, two extraction methods.
    clip:   page.get_text("words"/"text", clip=clip) for L and R  vs  the full page
    lines:  slot_text() for L and R (full-page lines assigned by centre)  vs  the full page
    Compared: word multisets (full page = page.get_text("words")) and non-whitespace character multisets."""
    doc = fitz.open(str(pdf_path))
    res = dict(spread_pages_checked=0, words_compared=0, chars_compared=0, words_crossing_cut=[],
               lines_crossing_cut=[], clip_mismatches=[], lines_mismatches=[])
    try:
        for i, page in enumerate(doc):
            full, clips = _page_slots(page)
            if len(clips) == 1:
                continue
            res["spread_pages_checked"] += 1
            fw = Counter(w[4] for w in full)
            fc = Counter(ch for ch in page.get_text("text") if not ch.isspace())
            res["words_compared"] += sum(fw.values())
            res["chars_compared"] += sum(fc.values())
            x = clips[0][1][2]
            cross = [w[4] for w in full if w[0] < x < w[2]]
            if cross:
                res["words_crossing_cut"].append((i + 1, cross))
            d = page.get_text("dict")
            lcross = ["".join(sp["text"] for sp in l["spans"]) for b in d["blocks"] if b["type"] == 0
                      for l in b["lines"] if l["bbox"][0] < x < l["bbox"][2]]
            if lcross:
                res["lines_crossing_cut"].append((i + 1, lcross))
            cw, cc, lw, lc = Counter(), Counter(), Counter(), Counter()
            for _, clip in clips:
                cw.update(w[4] for w in page.get_text("words", clip=clip))
                cc.update(ch for ch in page.get_text("text", clip=clip) if not ch.isspace())
                t = slot_text(page, clip, d)
                lw.update(w for w in RE_MUPDF_DELIM.split(t) if w)
                lc.update(ch for ch in t if not ch.isspace())
            for name, hw, hc in (("clip_mismatches", cw, cc), ("lines_mismatches", lw, lc)):
                if fw != hw or fc != hc:
                    res[name].append(dict(pdf_page=i + 1, words_lost=list((fw - hw).elements()),
                                          words_dup=list((hw - fw).elements()),
                                          chars_lost="".join((fc - hc).elements()),
                                          chars_dup="".join((hc - fc).elements())))
    finally:
        doc.close()
    return res


def analyze(pdf_path: str) -> dict:
    scan = _scan(str(pdf_path))
    rows = map_pages(pdf_path)
    k = scan["k"]
    total_votes = sum(scan["votes"].values())
    with_folio = [r for r in rows if r["detected_number"] is not None]
    agree = [r for r in with_folio if r["agrees"]]
    disagree = [r for r in with_folio if not r["agrees"]]
    no_folio = [r for r in rows if r["detected_number"] is None]
    # runs of consecutive slots sharing one offset (detected - k_page)
    runs, cur = [], None
    for r in with_folio:
        d = r["detected_number"] - r["k_page"]
        if cur and cur["delta"] == d:
            cur["last"] = (r["pdf_page"], r["side"], r["detected_number"])
            cur["n"] += 1
        else:
            cur = dict(delta=d, first=(r["pdf_page"], r["side"], r["detected_number"]),
                       last=(r["pdf_page"], r["side"], r["detected_number"]), n=1)
            runs.append(cur)
    detected_seq = [r["detected_number"] for r in with_folio]
    dup_detected = [v for v, n in Counter(detected_seq).items() if n > 1]
    printed = [r["printed_page"] for r in rows if r["printed_page"] is not None]
    single = [(r["pdf_page"], r["side"]) for r in rows
              if sum(1 for q in rows if q["pdf_page"] == r["pdf_page"]) == 1]
    return dict(
        k_1based=k, k_0based=k + 2, votes=scan["votes"].most_common(6), vote_share=scan["votes"][k] / total_votes,
        slots=len(rows), slots_with_folio=len(with_folio), match_rate=len(agree) / len(with_folio),
        disagreements=[(r["pdf_page"], r["side"], r["k_page"], r["detected_number"]) for r in disagree],
        no_folio_pages=sorted({r["pdf_page"] for r in no_folio}),
        no_folio_slots=[(r["pdf_page"], r["side"], r["k_page"], r["n_words"]) for r in no_folio],
        offset_runs=runs, duplicate_detected=dup_detected,
        first_detected=with_folio[0]["detected_number"] if with_folio else None,
        last_detected=with_folio[-1]["detected_number"] if with_folio else None,
        printed_range=(min(printed), max(printed)), single_width_pages=single,
        roman_hits=[(p["N"], c["text"]) for p in scan["pages"] for s in p["slots"] for c in s["folio_hits"]
                    if c["kind"] == "roman"],
    )


if __name__ == "__main__":
    import json
    for path in sys.argv[1:]:
        print(json.dumps(analyze(path), ensure_ascii=False, default=str, indent=1))
