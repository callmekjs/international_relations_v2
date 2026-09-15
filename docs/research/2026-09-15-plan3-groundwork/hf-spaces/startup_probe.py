"""Measure what a Space would pay at startup: import time and memory for gradio + openai + the corpus.
No network calls, no API key, repository opened read-only via sys.path."""
import json, os, sys, time, importlib.metadata as md
import psutil
REPO = r"C:/international_relations"
proc = psutil.Process()
def rss(): return round(proc.memory_info().rss / 2**20, 1)
out = {"python": sys.version.split()[0], "rss_start_mb": rss()}
t = time.perf_counter(); import gradio; out["import_gradio_s"] = round(time.perf_counter() - t, 2); out["rss_after_gradio_mb"] = rss()
t = time.perf_counter(); import openai, httpx, httpx2; out["import_openai_s"] = round(time.perf_counter() - t, 2); out["rss_after_openai_mb"] = rss()
out["versions"] = {p: md.version(p) for p in ["gradio", "gradio-client", "openai", "httpx", "httpx2", "huggingface-hub", "numpy", "bm25s", "fastapi", "starlette", "uvicorn", "pydantic"]}
sys.path.insert(0, REPO)
t = time.perf_counter()
from assistant.corpus import Corpus
c = Corpus(os.path.join(REPO, "corpus"))
out["load_corpus_s"] = round(time.perf_counter() - t, 2); out["rss_after_corpus_mb"] = rss()
t = time.perf_counter(); r = c.search("한미 정상회담", [2023], k=5); out["first_search_s"] = round(time.perf_counter() - t, 3)
out["search_hits"] = len(r.get("results", r.get("hits", [])) if isinstance(r, dict) else r)
# Build a Blocks app (no launch) to be sure gradio + openai coexist in one process
t = time.perf_counter()
with gradio.Blocks() as demo:
    gradio.Textbox(); gradio.Markdown("x")
out["build_blocks_s"] = round(time.perf_counter() - t, 3)
print(json.dumps(out, ensure_ascii=False, indent=1))
