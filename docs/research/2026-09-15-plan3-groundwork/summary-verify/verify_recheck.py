"""Verifier re-run of the citation check on a chapter-sized `shown` map. No LLM, no network.
Saves only counts, grades and timings (no white-paper text)."""
from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, "C:/international_relations")
from assistant.citations import ShownPage, cite_key, verify_answer  # noqa: E402

HERE = Path(__file__).resolve().parent
rows = [json.loads(l) for l in open("C:/international_relations/corpus/pages.jsonl", encoding="utf-8")]


def paras(text):
    return [line for line in text.split("\n") if line.strip()]


def label(p):
    return f"{p['year']}년치 · 「{p['edition_title']}」 {p['printed_page']}쪽" + ("" if p["label_printed"] else "(번호 미인쇄)")


def chapter(year, lab):
    pages = [r for r in rows if r["year"] == year and r["chapter_label"] == lab and r["citable"]]
    shown = {p["page_id"]: ShownPage(p["page_id"], p["year"], label(p), tuple(paras(p["text"]))) for p in pages}
    return pages, shown


def word_quote(text, rng, lo=20, hi=50):
    """A quote cut at spaces (like a model would copy a phrase)."""
    words = text.split(" ")
    for _ in range(50):
        i = rng.randrange(len(words))
        j = i + 1
        while j <= len(words) and len(" ".join(words[i:j])) < lo:
            j += 1
        q = " ".join(words[i:j])
        if lo <= len(q) <= hi + 30:
            return q
    return text[:hi]


def regroup(answer, verify):
    flat = [s for sec in answer["sections"] for s in sec["sentences"]] + answer["overview"]
    checked = verify({"status": "answered", "sentences": flat}, SHOWN)
    out, i = [], 0
    for sec in answer["sections"]:
        n = len(sec["sentences"])
        out.append(checked["sentences"][i:i + n])
        i += n
    return out, checked["sentences"][i:], checked


results = {}
rng = random.Random(915)
for year, lab in ((2023, "제3장"), (2025, "제7장")):
    pages, SHOWN = chapter(year, lab)
    body = [(p, n, t) for p in pages for n, t in enumerate(paras(p["text"]), 1) if len(t) >= 120]
    # 1. exact word-boundary quotes from long paragraphs: all should verify
    exact = []
    for p, n, t in rng.sample(body, min(200, len(body))):
        exact.append({"text": "x", "citations": [{"page_id": p["page_id"], "paragraph": n, "quote": word_quote(t, rng)}]})
    t0 = time.perf_counter()
    chk = verify_answer({"status": "answered", "sentences": exact}, SHOWN)
    t_exact = time.perf_counter() - t0
    reasons = Counter(c["citations"][0]["reason"] for c in chk["sentences"])
    # 2. the same quotes, but the page_id is a different page of the same chapter -> moved_page
    moved = []
    for s in exact[:50]:
        c = dict(s["citations"][0])
        other = rng.choice([pid for pid in SHOWN if pid != c["page_id"]])
        moved.append({"text": "x", "citations": [{**c, "page_id": other, "paragraph": 1}]})
    chk2 = verify_answer({"status": "answered", "sentences": moved}, SHOWN)
    reasons2 = Counter((c["citations"][0]["grade"], c["citations"][0]["reason"]) for c in chk2["sentences"])
    # 3. a quote spanning two consecutive numbered paragraphs (joined by a space) -> should NOT verify
    span = []
    for p in pages:
        ps = paras(p["text"])
        for k in range(len(ps) - 1):
            if len(ps[k]) >= 40 and len(ps[k + 1]) >= 40:
                span.append({"text": "x", "citations": [{"page_id": p["page_id"], "paragraph": k + 1,
                                                          "quote": ps[k][-20:] + " " + ps[k + 1][:20]}]})
                break
        if len(span) >= 50:
            break
    chk3 = verify_answer({"status": "answered", "sentences": span}, SHOWN)
    reasons3 = Counter((c["citations"][0]["grade"], c["citations"][0]["reason"]) for c in chk3["sentences"])
    # 4. worst case the schema allows: 12 sections x 8 sentences + 3 overview, 3 absent citations each
    miss = lambda: {"page_id": rng.choice(list(SHOWN)), "paragraph": 1, "quote": "존재하지않는구절입니다정말로없음"}  # noqa: E731
    answer = {"sections": [{"title": f"s{i}", "sentences": [{"text": "x", "citations": [miss(), miss(), miss()]}
                                                            for _ in range(8)]} for i in range(12)],
              "overview": [{"text": "x", "citations": [miss(), miss(), miss()]} for _ in range(3)]}
    t0 = time.perf_counter()
    secs, ov, ck = regroup(answer, verify_answer)
    t_worst = time.perf_counter() - t0
    # 5. realistic miss: 27 sentences x 2 absent citations
    answer2 = {"sections": [{"title": "s", "sentences": [{"text": "x", "citations": [miss(), miss()]} for _ in range(4)]}
                            for _ in range(6)], "overview": [{"text": "x", "citations": [miss(), miss()]} for _ in range(3)]}
    t0 = time.perf_counter()
    regroup(answer2, verify_answer)
    t_real = time.perf_counter() - t0
    # 6. duplicate paragraph texts inside the chapter (a quote could verify on the wrong page)
    keys = Counter(cite_key(t) for p in pages for t in paras(p["text"]) if len(t) >= 40)
    dup = sum(1 for k, c in keys.items() if c > 1)
    results[f"{year} {lab}"] = {
        "pages": len(pages), "long_paragraphs": len(body),
        "exact_word_quotes": {"n": len(exact), "reasons": dict(reasons), "seconds": round(t_exact, 3)},
        "moved_page": {"n": len(moved), "grades": {f"{g}/{r}": v for (g, r), v in reasons2.items()}},
        "quote_across_two_paragraphs": {"n": len(span), "grades": {f"{g}/{r}": v for (g, r), v in reasons3.items()}},
        "schema_worst_case_297_absent_citations_seconds": round(t_worst, 3),
        "regroup_lengths": [len(s) for s in secs], "overview": len(ov),
        "realistic_miss_54_absent_citations_seconds": round(t_real, 3),
        "duplicate_long_paragraph_keys_in_chapter": dup,
    }
(HERE / "verify_recheck_output.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=1))
