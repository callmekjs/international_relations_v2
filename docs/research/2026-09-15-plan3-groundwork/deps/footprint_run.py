"""Run footprint_step.py modes in fresh subprocesses (3 repetitions) and check the corpus is unchanged."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = Path("C:/international_relations/corpus")


def snapshot():
    rows = {}
    for p in sorted(CORPUS.rglob("*")):
        if p.is_file():
            st = p.stat()
            rows[str(p.relative_to(CORPUS)).replace("\\", "/")] = {"bytes": st.st_size, "mtime": st.st_mtime_ns,
                                                                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16]}
    return rows


before = snapshot()
env = {**os.environ, "PYTHONUTF8": "1", "GRADIO_ANALYTICS_ENABLED": "False", "HF_HUB_DISABLE_TELEMETRY": "1",
       "HF_HUB_OFFLINE": "1", "NO_PROXY": "127.0.0.1,localhost"}
env.pop("OPENAI_API_KEY", None)
results = []
for rep in range(int(os.environ.get("FP_REPS", "3"))):
    for i, mode in enumerate(["bare", "numpy_bm25s", "corpus", "gradio", "app"]):
        env["FP_PORT"] = str(7871 + i)
        done = subprocess.run([sys.executable, str(HERE / "footprint_step.py"), mode], env=env, capture_output=True,
                              text=True, encoding="utf-8", timeout=300)
        line = [l for l in done.stdout.splitlines() if l.startswith("RESULT ")]
        if not line:
            print("FAILED", mode, done.stdout[-2000:], done.stderr[-2000:])
            continue
        r = json.loads(line[0][7:])
        r["rep"] = rep
        results.append(r)
        last = r["steps"][-1]["mem"]
        print(rep, mode, "total_s", r["total_s"], "last mem", last, flush=True)
after = snapshot()
out = {"corpus_files": before, "corpus_unchanged": before == after,
       "corpus_total_bytes": sum(v["bytes"] for v in before.values()), "corpus_file_count": len(before),
       "runs": results}
(HERE / os.environ.get("FP_OUT", "footprint_results.json")).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("corpus_unchanged", out["corpus_unchanged"], "bytes", out["corpus_total_bytes"], "files", out["corpus_file_count"])
