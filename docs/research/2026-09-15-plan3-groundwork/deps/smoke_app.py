"""Tiny Gradio Blocks app that also imports openai (httpx2) and builds a client with a FAKE key.
No OpenAI request is made. Streams fake progress lines from a worker thread, like assistant.run(on_event)."""
import json
import os
import queue
import sys
import threading
import time

t0 = time.perf_counter()
import httpx
import httpx2
import openai
from openai import OpenAI
import gradio as gr
import gradio_client
t_import = time.perf_counter() - t0

from memwin import mem_mb

client = OpenAI(api_key="sk-fake-never-used", max_retries=0, timeout=180.0)  # never used for a request
INFO = {
    "python": sys.version.split()[0], "gradio": gr.__version__, "gradio_client": gradio_client.__version__,
    "openai": openai.__version__, "httpx": httpx.__version__, "httpx2": httpx2.__version__,
    "openai_http_client": f"{type(client._client).__module__}.{type(client._client).__name__}",
    "import_s": round(t_import, 2),
}


def fake_run(question: str, on_event) -> str:
    for kind, summary in [("thinking", "생각 중"), ("tool_finished", "목차 보기 2023년치"),
                          ("tool_finished", "찾기 \"한미 정상회담\""), ("answer_started", "답 정리 중")]:
        time.sleep(0.2)
        on_event(kind, summary=summary)
    return f"(가짜 답) {question}"


def ask(question: str, request: gr.Request):
    events: queue.Queue = queue.Queue()
    box: dict = {}

    def worker():
        box["answer"] = fake_run(question, lambda kind, **data: events.put((kind, data)))
        events.put(("done", {}))

    threading.Thread(target=worker, daemon=True).start()
    lines = []
    while True:
        kind, data = events.get()
        if kind == "done":
            break
        lines.append(f"- {data['summary']}")
        yield "\n".join(lines), ""
    host = request.client.host if request and request.client else None
    yield "\n".join(lines), json.dumps({"answer": box["answer"], "client_host_seen": bool(host)}, ensure_ascii=False)


with gr.Blocks(title="deps smoke") as demo:
    q = gr.Textbox(label="질문")
    progress = gr.Markdown()
    out = gr.Textbox(label="답")
    gr.Button("묻기").click(ask, q, [progress, out], api_name="ask")
    info = gr.JSON(value=lambda: {**INFO, "mem_mb": mem_mb()})
    gr.Button("info").click(lambda: {**INFO, "mem_mb": mem_mb()}, None, info, api_name="info")

if __name__ == "__main__":
    port = int(os.environ.get("SMOKE_PORT", "7861"))
    print("READY_TO_LAUNCH", json.dumps({**INFO, "mem_mb_before_launch": mem_mb()}), flush=True)
    demo.queue(default_concurrency_limit=4).launch(server_name="127.0.0.1", server_port=port, show_error=True,
                                                   prevent_thread_lock=False)
