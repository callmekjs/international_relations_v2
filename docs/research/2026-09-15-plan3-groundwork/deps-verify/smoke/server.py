import os, sys, time, json, threading, queue
t0 = time.perf_counter()
import httpx, httpx2, openai
from openai import OpenAI
import gradio as gr
t_import = time.perf_counter() - t0
port = int(sys.argv[1]); ssr = sys.argv[2] == "ssr"
client = OpenAI(api_key="sk-fake-never-used", base_url="https://mock.invalid/v1", max_retries=0, timeout=180)

def fake_run(question, on_event):
    for kind, label in [("thinking","생각 중"),("tool_requested","목차 보기"),("tool_finished","찾기 끝"),("answer_started","답 정리 중"),("done","끝")]:
        time.sleep(0.25); on_event(kind, label)
    return {"answer": f"(fake) {question}"}

def ask(question, request: gr.Request):
    q = queue.Queue(); lines = []
    out = {}
    def worker():
        out["r"] = fake_run(question, lambda k, l: q.put(l)); q.put(None)
    threading.Thread(target=worker, daemon=True).start()
    while True:
        item = q.get()
        if item is None: break
        lines.append(item); yield "\n".join(lines), ""
    yield "\n".join(lines), json.dumps({**out["r"], "host": bool(request.client and request.client.host)}, ensure_ascii=False)

def info():
    import ctypes
    from ctypes import wintypes
    class PMC(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD),("PeakWorkingSetSize",ctypes.c_size_t),("WorkingSetSize",ctypes.c_size_t),("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t)]
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    import importlib.metadata as md
    return json.dumps({"pid": os.getpid(), "ws_mb": round(c.WorkingSetSize/2**20,1), "import_s": round(t_import,2),
        "versions": {p: md.version(p) for p in ["gradio","gradio_client","openai","httpx","httpx2","pydantic"]},
        "openai_client_base": type(client._client).__mro__[2].__module__ + "." + type(client._client).__mro__[2].__name__,
        "mcp_loaded": "mcp" in sys.modules, "ssr": ssr})

with gr.Blocks() as demo:
    q = gr.Textbox(); prog = gr.Markdown(); ans = gr.Textbox()
    gr.Button("ask").click(ask, q, [prog, ans], api_name="ask")
    gr.Button("info").click(info, None, ans, api_name="info")
demo.queue()
demo.launch(server_name="127.0.0.1", server_port=port, ssr_mode=ssr, quiet=False)
