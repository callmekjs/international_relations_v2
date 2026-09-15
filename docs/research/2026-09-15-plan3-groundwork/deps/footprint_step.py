"""One measurement process. argv[1] = mode. Prints one JSON line: seconds and memory (MB) after each step.
Loads the real corpus READ-ONLY from C:/international_relations/corpus; code comes from repo_copy/."""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "repo_copy"))
sys.path.insert(0, str(HERE))
from memwin import mem_mb

CORPUS = Path("C:/international_relations/corpus")
mode = sys.argv[1]
steps = [{"step": "start", "s": 0.0, "mem": mem_mb()}]


def step(name, fn):
    t = time.perf_counter()
    out = fn()
    steps.append({"step": name, "s": round(time.perf_counter() - t, 3), "mem": mem_mb()})
    return out


def load_corpus():
    from assistant.corpus import Corpus
    return Corpus(CORPUS)


def use_corpus(c):
    hits = c.search("한미 정상회담", [2023], k=10)
    pages = c.read_pages([h["page_id"] for h in hits["hits"][:5]])
    toc = c.get_toc(2023)
    multi = c.search("기후변화", [2020, 2021, 2022, 2023, 2024, 2025], k=10)
    return {"hits": len(hits["hits"]), "pages": len(pages["pages"]), "toc": len(toc["entries"]),
            "multi_hits": len(multi["hits"]), "n_pages": len(c.pages)}


def build_blocks():
    import gradio as gr
    with gr.Blocks(title="footprint") as demo:
        with gr.Tabs():
            for name in ["질문답변", "요약", "표 뽑기", "비교", "예시 모음"]:
                with gr.Tab(name):
                    box = gr.Textbox(label="입력")
                    md = gr.Markdown()
                    out = gr.JSON()
                    gr.Button("실행").click(lambda text: (f"- {text}", {"echo": text}), box, [md, out])
    return demo


def openai_client():
    from openai import OpenAI
    from assistant.llm_openai import OpenAIResponses
    return OpenAIResponses(OpenAI(api_key="sk-fake-never-used", max_retries=0, timeout=180.0))


def launch_and_get(demo):
    import httpx
    demo.queue(default_concurrency_limit=4).launch(server_name="127.0.0.1", server_port=int(os.environ.get("FP_PORT", "7871")),
                                                   prevent_thread_lock=True, quiet=True)
    r = httpx.get(f"http://127.0.0.1:{os.environ.get('FP_PORT', '7871')}/", timeout=10)
    return r.status_code


info = {"mode": mode}
if mode == "bare":
    pass
elif mode == "numpy_bm25s":
    step("import numpy+bm25s", lambda: __import__("bm25s"))
elif mode == "corpus":
    step("import assistant.corpus", lambda: __import__("assistant.corpus"))
    c = step("Corpus(corpus/)", load_corpus)
    info["use"] = step("search x2 + read_pages + get_toc", lambda: use_corpus(c))
elif mode == "gradio":
    step("import gradio", lambda: __import__("gradio"))
    step("import openai + client", openai_client)
    demo = step("build Blocks (5 tabs)", build_blocks)
    info["http"] = step("launch + GET /", lambda: launch_and_get(demo))
elif mode == "app":
    step("import assistant.corpus", lambda: __import__("assistant.corpus"))
    c = step("Corpus(corpus/)", load_corpus)
    info["use"] = step("search x2 + read_pages + get_toc", lambda: use_corpus(c))
    step("import gradio", lambda: __import__("gradio"))
    step("import openai + client", openai_client)
    demo = step("build Blocks (5 tabs)", build_blocks)
    info["http"] = step("launch + GET /", lambda: launch_and_get(demo))
else:
    raise SystemExit(f"unknown mode {mode}")
info["steps"] = steps
info["total_s"] = round(sum(s["s"] for s in steps), 3)
print("RESULT " + json.dumps(info, ensure_ascii=False), flush=True)
os._exit(0)  # do not wait for the uvicorn thread
