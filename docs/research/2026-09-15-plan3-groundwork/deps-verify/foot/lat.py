import json, sys, time, statistics
sys.path.insert(0, sys.argv[1])
from assistant.corpus import Corpus
c = Corpus(sys.argv[2])
qs = [json.loads(l) for l in open(sys.argv[1] + "/tests/fixtures/search_queries.jsonl", encoding="utf-8")]
key = sys.argv[3]
res = {}
for label, years in [("all", None), ("one", [2023]), ("six", [2020,2021,2022,2023,2024,2025])]:
    ts = []
    for _ in range(3):
        for q in qs:
            t = time.perf_counter(); c.search(q[key], years=years); ts.append((time.perf_counter()-t)*1000)
    ts.sort(); res[label] = {"n": len(ts), "median_ms": round(statistics.median(ts),3), "p95_ms": round(ts[int(len(ts)*0.95)-1],3), "max_ms": round(ts[-1],3)}
print(key, len(qs), json.dumps(res))
