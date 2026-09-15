"""Search / read_pages latency on the real corpus (read-only), single thread. Queries from tests/fixtures/search_queries.jsonl."""
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "repo_copy"))
from assistant.corpus import Corpus

c = Corpus(Path("C:/international_relations/corpus"))
rows = [json.loads(l) for l in open(HERE / "repo_copy/tests/fixtures/search_queries.jsonl", encoding="utf-8")]
queries = []
for r in rows:
    q = r.get("query") or r.get("q") or r.get("question")
    y = r.get("years") or ([r["year"]] if "year" in r else None)
    if q:
        queries.append((q, y))
times_one, times_all, times_multi = [], [], []
for _ in range(3):
    for q, y in queries:
        t = time.perf_counter(); c.search(q, None, k=10); times_all.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter(); c.search(q, [2023], k=10); times_one.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter(); c.search(q, [2020, 2021, 2022, 2023, 2024, 2025], k=10); times_multi.append((time.perf_counter() - t) * 1000)
ids = [pid for pid, pg in c.pages.items() if pg["citable"]][500:505]
t = time.perf_counter()
for _ in range(200):
    assert len(c.read_pages(ids)["pages"]) == 5
read_ms = (time.perf_counter() - t) * 1000 / 200


def p(v):
    v = sorted(v)
    return {"median_ms": round(statistics.median(v), 2), "p95_ms": round(v[int(len(v) * 0.95) - 1], 2), "max_ms": round(v[-1], 2)}


out = {"queries": len(queries), "reps": 3, "all_years": p(times_all), "one_year": p(times_one),
       "six_years_balanced": p(times_multi), "read_pages_5_ms": round(read_ms, 3)}
print(json.dumps(out, ensure_ascii=False))
(HERE / "search_latency.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
