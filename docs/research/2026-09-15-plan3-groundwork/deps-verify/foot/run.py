import hashlib, json, os, socket, subprocess, sys, statistics
py, code, corpus, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def snap():
    r = {}
    for root, _, files in os.walk(corpus):
        for f in files:
            p = os.path.join(root, f); st = os.stat(p)
            r[p] = (hashlib.sha256(open(p, "rb").read()).hexdigest(), st.st_mtime_ns, st.st_size)
    return r
before = snap()
env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
env.update(GRADIO_ANALYTICS_ENABLED="False", HF_HUB_OFFLINE="1", PYTHONUTF8="1")
res = {}
for mode in ["full", "corpus", "gradio", "full_blas1"]:
    runs = []
    for i in range(3):
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        e = dict(env)
        m = mode
        if mode == "full_blas1": e["OPENBLAS_NUM_THREADS"] = "1"; m = "full"
        p = subprocess.run([py, os.path.join(os.path.dirname(__file__), "step.py"), m, code, corpus, str(port)], capture_output=True, text=True, encoding="utf-8", env=e, timeout=300)
        line = [l for l in p.stdout.splitlines() if l.startswith("{")]
        if not line: print(p.stdout[-2000:], p.stderr[-3000:]); raise SystemExit(1)
        runs.append(json.loads(line[-1])["rows"])
    agg = []
    for j, row in enumerate(runs[0]):
        a = {"step": row["step"]}
        for key in ("s", "ws_mb", "private_mb", "ms_each"):
            if key in row: a[key] = statistics.median(r[j][key] for r in runs)
        agg.append(a)
    res[mode] = agg
res["corpus_unchanged"] = before == snap()
res["corpus_files"] = len(before); res["corpus_bytes"] = sum(v[2] for v in before.values())
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for mode in ["full", "corpus", "gradio", "full_blas1"]:
    print("==", mode)
    for a in res[mode]: print("  ", a)
print("corpus_unchanged", res["corpus_unchanged"], res["corpus_files"], res["corpus_bytes"])
