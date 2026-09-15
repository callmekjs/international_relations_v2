"""What a default launch() exposes (monitoring summary, run history, API info) on 127.0.0.1:7863."""
import json, sys, time
import httpx
import gradio as gr

with gr.Blocks() as demo:
    t = gr.Textbox()
    t.submit(lambda x: x, t, t)
demo.queue()
demo.launch(server_name="127.0.0.1", server_port=7863, prevent_thread_lock=True, quiet=True)
out = {}
B = "http://127.0.0.1:7863"
for path in ("/monitoring/summary", "/gradio_api/runs", "/gradio_api/info"):
    r = httpx.get(B + path, timeout=10)
    out[path] = {"status": r.status_code, "body": r.text[:160]}
cfg = httpx.get(B + "/config", timeout=10).json()
out["config"] = {k: cfg.get(k) for k in ("footer_links", "run_history", "analytics_enabled", "show_error", "pwa", "mcp_server")}
print(json.dumps(out, ensure_ascii=False, indent=1))
demo.close()
