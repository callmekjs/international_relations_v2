"""Adversarial probes against the other agent's citation_check.py (copied to ./orig, unmodified).
Offline. Run from C:/international_relations with PYTHONUTF8=1 and PYTHONPATH=<this folder>/orig.
Special characters are built with chr() on purpose (tool-written files can lose escape sequences)."""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

from assistant.corpus import Corpus
from citation_check import cite_key, keyed, verify_answer

ELL = chr(0x2026)
LDQ, RDQ = chr(0x201C), chr(0x201D)
DOT = chr(0xB7)

corpus = Corpus(Path("corpus"))
rng = random.Random(4242)
citable = [p for p in corpus.pages.values() if p["citable"]]
by_year = {}
for p in citable:
    by_year.setdefault(p["year"], []).append(p)
order = list(corpus.pages)
index = {pid: i for i, pid in enumerate(order)}
OUT = {}


def run(page_id, quote, read_ids, **kw):
    reads = [corpus.read_pages(read_ids[i:i + 5]) for i in range(0, len(read_ids), 5)]
    ans = {"status": "answered", "sentences": [{"text": "x", "citations": [{"page_id": page_id, "quote": quote}]}]}
    s = verify_answer(ans, corpus, reads, **kw)["sentences"][0]
    return s, s["citations"][0]


def word_quote(text, lo=15, hi=100):
    """A verbatim span that starts and ends at spaces/line breaks, like a model would copy."""
    flat = text
    bounds = [0] + [m.end() for m in re.finditer(r"[ \n]", flat)]
    for _ in range(50):
        a = rng.choice(bounds)
        ends = [m.start() for m in re.finditer(r"[ \n]", flat[a:])] + [len(flat) - a]
        ends = [e for e in ends if lo <= e <= hi]
        if ends:
            e = rng.choice(ends)
            q = flat[a:a + e].strip()
            if len(q) >= lo:
                return q
    return None


# P1: random verbatim quotes (word boundaries, all years), page + 4 random same-year pages read.
def p1(n=1500):
    stats, fails = Counter(), []
    for _ in range(n):
        page = rng.choice(citable)
        q = word_quote(page["text"])
        if not q:
            continue
        others = [x["page_id"] for x in rng.sample(by_year[page["year"]], 4) if x["page_id"] != page["page_id"]]
        s, c = run(page["page_id"], q, [page["page_id"]] + others)
        crosses = "\n" in q
        stats[(c["quote_status"], "multi-line" if crosses else "one-line")] += 1
        if c["quote_status"] != "exact" and not (c["quote_status"] == "exact_on_other_page"):
            fails.append((page["page_id"], q, c["quote_status"], c["similarity"]))
    OUT["P1_random_verbatim"] = {"counts": {f"{k[0]}|{k[1]}": v for k, v in stats.items()}, "non_exact_examples": fails[:8]}


# P1b: random verbatim quotes at arbitrary character boundaries (not word boundaries).
def p1b(n=1500):
    stats, fails = Counter(), []
    for _ in range(n):
        page = rng.choice(citable)
        t = page["text"]
        if len(t) < 60:
            continue
        L = rng.randint(15, 60)
        a = rng.randrange(0, len(t) - L)
        q = t[a:a + L]
        s, c = run(page["page_id"], q, [page["page_id"]])
        stats[c["quote_status"]] += 1
        if c["quote_status"] not in ("exact", "too_short"):
            fails.append((page["page_id"], q, c["quote_status"], c["similarity"]))
    OUT["P1b_random_char_slices"] = {"counts": dict(stats), "non_exact_examples": fails[:8]}


# P2: model habits on otherwise verbatim quotes.
def p2(n=300):
    variants = {
        "leading_ellipsis": lambda q: ELL + q,
        "trailing_ellipsis": lambda q: q + ELL,
        "leading_dots": lambda q: "..." + q,
        "curly_quotes_wrap": lambda q: LDQ + q + RDQ,
        "trailing_period_added": lambda q: q + ".",
        "line_break_removed_no_space": lambda q: q.replace("\n", ""),
    }
    stats = {k: Counter() for k in variants}
    for _ in range(n):
        page = rng.choice(citable)
        q = word_quote(page["text"], 20, 80)
        if not q or q.endswith("."):
            continue
        for name, f in variants.items():
            s, c = run(page["page_id"], f(q), [page["page_id"]])
            stats[name][s["badge"] + "/" + str(c["quote_status"])] += 1
    OUT["P2_model_habits"] = {k: dict(v) for k, v in stats.items()}


# P3: meaning-flipping edits on real lines.
SWAPS = [("증가", "감소"), ("확대", "축소"), ("강화", "약화"), ("상승", "하락"), ("찬성", "반대"), ("지지", "반대"),
         ("체결", "파기"), ("개최", "취소"), ("참석", "불참"), ("흑자", "적자"), ("미국", "중국"), ("일본", "중국"),
         ("남한", "북한"), ("최초", "최후"), ("두 차례", "세 차례"), ("첫", "두 번째"), ("승인", "거부"), ("동의", "거부")]


def p3(per_swap=25):
    rows, totals = {}, Counter()
    for old, new in SWAPS:
        c_stats = Counter()
        pool = [p for p in citable if old in p["text"]]
        rng.shuffle(pool)
        for page in pool[:per_swap]:
            t = page["text"]
            j = t.find(old)
            a = max(0, j - rng.randint(10, 30))
            b = min(len(t), j + len(old) + rng.randint(10, 30))
            q = t[a:b].replace("\n", " ").strip()
            bad = q.replace(old, new, 1)
            s, c = run(page["page_id"], bad, [page["page_id"]])
            c_stats[s["badge"]] += 1
            totals[s["badge"]] += 1
        rows[f"{old}->{new}"] = dict(c_stats)
    # negation insertion: '했다' -> '하지 않았다'
    neg = Counter()
    pool = [p for p in citable if "했다" in p["text"]]
    rng.shuffle(pool)
    for page in pool[:60]:
        t = page["text"]
        j = t.find("했다")
        q = t[max(0, j - 30):j + 2].replace("\n", " ").strip()
        bad = q[:-2] + "하지 않았다"
        s, c = run(page["page_id"], bad, [page["page_id"]])
        neg[s["badge"]] += 1
        totals[s["badge"]] += 1
    rows["했다->하지 않았다"] = dict(neg)
    OUT["P3_meaning_flips"] = {"per_swap": rows, "total": dict(totals)}


# P4: the same sentence appears in two different years; cite the wrong-year page (both read).
def p4(max_pairs=40):
    keys_by_year = {}
    found = []
    lines_seen = {}
    for p in citable:
        for ln in p["text"].split("\n"):
            ln = ln.strip()
            if 40 <= len(ln) <= 120:
                lines_seen.setdefault(cite_key(ln), []).append((p["year"], p["page_id"], ln))
    for k, occ in lines_seen.items():
        years = {y for y, _, _ in occ}
        if len(years) >= 2:
            found.append(occ)
    results = Counter()
    examples = []
    for occ in found[:max_pairs]:
        (y1, pid1, ln1) = occ[0]
        other = next(o for o in occ if o[0] != y1)
        (y2, pid2, ln2) = other
        # model reads both, cites the second page, but the quote is taken from a line present on both -> exact on cited.
        # Harder: quote exists only on pid1, cite pid2 (also read) -> corrected to another year.
        page2 = corpus.pages[pid2]["text"]
        page1 = corpus.pages[pid1]["text"]
        only1 = [l for l in page1.split("\n") if len(l.strip()) >= 25 and cite_key(l) not in cite_key(page2)]
        if not only1:
            continue
        q = only1[0].strip()[:60]
        s, c = run(pid2, q, [pid1, pid2])
        results[(c["quote_status"], c["corrected"], corpus.pages[c["evidence_page_ids"][0]]["year"] != corpus.pages[pid2]["year"] if c["evidence_page_ids"] else None)] += 1
        if c["corrected"] and len(examples) < 3:
            examples.append({"cited": pid2, "shown_as": c["label"], "quote": q})
    OUT["P4_cross_year"] = {"line_pairs_shared_across_years": len(found),
                            "wrong_year_citation_results": {str(k): v for k, v in results.items()},
                            "examples": examples}


# P5: how specific are short quotes? share of 8..14-key-char windows present on another same-year page.
def p5(n=400):
    year_keys = {y: [(p["page_id"], cite_key(p["text"])) for p in ps] for y, ps in by_year.items()}
    res = {}
    for L in (8, 10, 12, 15, 20):
        multi = 0
        tried = 0
        for _ in range(n):
            page = rng.choice(citable)
            k = cite_key(page["text"])
            if len(k) < L + 5:
                continue
            a = rng.randrange(0, len(k) - L)
            w = k[a:a + L]
            tried += 1
            if any(w in kk for pid, kk in year_keys[page["year"]] if pid != page["page_id"]):
                multi += 1
        res[f"{L}_key_chars"] = f"{multi}/{tried} also on another page of the same year"
    OUT["P5_short_quote_specificity"] = res


# P6: digit folding and digit-boundary false 'exact'.
def p6():
    cases = [
        ("2023-p147L", "제12차 출장단은", "middle dot between digits deleted: '제1" + DOT + "2차' read as '제12차'"),
        ("2024-p171R", "카이로 메트로 23호선", "'2" + DOT + "3호선' read as '23호선'"),
        ("2021-p112R", "7명(일반 외교 44명, 지역 외교 3명)", "leading digit dropped from '47명'"),
        ("2021-p112R", "6주 동안 운영했다", "leading digit dropped from '46주'"),
        ("2020-p006R", "경제성장률은 미국 3.5%, 유로존 6.6%를 기록하는 등", "minus signs dropped (control)"),
    ]
    rows = []
    for pid, q, why in cases:
        s, c = run(pid, q, [pid])
        rows.append({"page": pid, "quote": q, "why": why, "badge": s["badge"], "quote_status": c["quote_status"],
                     "evidence_shown": c["evidence"]})
    OUT["P6_digit_folding"] = rows


# P7: quote across a PDF-page boundary (R half -> next L half), and page-break join when cited page is the second half.
def p7(n=200):
    stats = Counter()
    ex = []
    for _ in range(n):
        i = rng.randrange(0, len(order) - 1)
        a, b = order[i], order[i + 1]
        pa, pb = corpus.pages[a], corpus.pages[b]
        if not (pa["citable"] and pb["citable"] and pa["year"] == pb["year"]):
            continue
        ta, tb = pa["text"].rstrip(), pb["text"].lstrip()
        if len(ta) < 30 or len(tb) < 30:
            continue
        q = ta[-rng.randint(12, 25):] + "\n" + tb[:rng.randint(12, 25)]
        kind = "R->nextL" if a.endswith("R") else "L->R"
        cited = rng.choice([a, b])
        s, c = run(cited, q, [a, b])
        stats[(kind, c["quote_status"])] += 1
        if c["quote_status"] not in ("joined",) and len(ex) < 4:
            ex.append((a, b, cited, q, c["quote_status"]))
    OUT["P7_page_break"] = {"counts": {f"{k[0]}|{k[1]}": v for k, v in stats.items()}, "non_joined_examples": ex}


# P8: near false positives on the hardest pairs: most similar page of a DIFFERENT year (annual repeated text).
def p8(n_pages=150):
    from assistant.textnorm import bigram_tokens
    bags = {p["page_id"]: Counter(bigram_tokens(p["text"])) for p in citable}
    sample = rng.sample(citable, n_pages)
    stats = Counter()
    examples = []
    for page in sample:
        bag = bags[page["page_id"]]
        best, score = None, 0
        for q in citable:
            if q["year"] == page["year"]:
                continue
            inter = sum((bag & bags[q["page_id"]]).values())
            if inter > score:
                best, score = q, inter
        for _ in range(3):
            qt = word_quote(page["text"], 25, 70)
            if not qt:
                continue
            s, c = run(best["page_id"], qt, [best["page_id"]])
            stats[s["badge"] + "/" + str(c["quote_status"])] += 1
            if s["grade"] in ("near", "verified") and len(examples) < 6:
                examples.append({"quote_from": page["page_id"], "cited": best["page_id"], "quote": qt,
                                 "badge": s["badge"], "evidence": c["evidence"], "diff": c["differences"]})
    OUT["P8_cross_year_near"] = {"counts": dict(stats), "examples": examples}


# P9: quoting the section/chapter title the model saw in read_pages metadata.
def p9(n=200):
    stats = Counter()
    for _ in range(n):
        page = rng.choice(citable)
        title = page["section_title"] or page["chapter_title"]
        if not title or len(cite_key(title)) < 8:
            continue
        s, c = run(page["page_id"], title, [page["page_id"]])
        stats[c["quote_status"]] += 1
    OUT["P9_metadata_title_quotes"] = dict(stats)


for f in (p1, p1b, p2, p3, p4, p5, p6, p7, p8, p9):
    f()
    print(f.__name__, "done", file=sys.stderr)
json.dump(OUT, sys.stdout, ensure_ascii=False, indent=1)
print()
