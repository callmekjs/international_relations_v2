"""Timing of verify_answer per absent citation on 2023 제3장 (verifier). No text saved."""
import json, sys, time, random, statistics
sys.path.insert(0, "C:/international_relations")
from assistant.citations import ShownPage, verify_answer
rows = [json.loads(l) for l in open("C:/international_relations/corpus/pages.jsonl", encoding="utf-8")]
pages = [r for r in rows if r["year"] == 2023 and r["chapter_label"] == "제3장" and r["citable"]]
P = lambda t: [x for x in t.split("\n") if x.strip()]
shown = {p["page_id"]: ShownPage(p["page_id"], 2023, "l", tuple(P(p["text"]))) for p in pages}
rng = random.Random(1)
out = {}
for style in ("fixed_absent", "reversed_plus_suffix"):
    for n in (1, 25, 54):
        times = []
        for rep in range(3):
            sents = []
            for i in range(n):
                p = rng.choice(pages); ps = P(p["text"]); k = rng.randrange(len(ps))
                q = "존재하지않는구절입니다정말로없음" if style == "fixed_absent" else ps[k][10:45][::-1] + "없는말없는말없는말"
                sents.append({"text": "x", "citations": [{"page_id": p["page_id"], "paragraph": k + 1, "quote": q}]})
            t0 = time.perf_counter(); r = verify_answer({"status": "answered", "sentences": sents}, shown); times.append(time.perf_counter() - t0)
        out[f"{style} n={n}"] = {"median_s": round(statistics.median(times), 3), "grades": dict(r["counts"])}
print(json.dumps(out, indent=1))
json.dump(out, open("timing_recheck_output.json", "w"), indent=1)
