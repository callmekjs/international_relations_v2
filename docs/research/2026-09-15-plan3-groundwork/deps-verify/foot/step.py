"""One fresh process: measure working set / private bytes after each step. argv: mode (full|corpus|gradio), codedir, corpusdir"""
import ctypes, json, os, sys, time
from ctypes import wintypes
class PMC(ctypes.Structure):
    _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD),("PeakWorkingSetSize",ctypes.c_size_t),("WorkingSetSize",ctypes.c_size_t),("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t),("PrivateUsage",ctypes.c_size_t)]
k32 = ctypes.WinDLL("kernel32"); psapi = ctypes.WinDLL("psapi")
k32.GetCurrentProcess.restype = wintypes.HANDLE
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
def mem():
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    assert psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return round(c.WorkingSetSize/2**20,1), round(c.PrivateUsage/2**20,1)
mode, code, corpus_dir = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, code)
rows = []
def rec(name, t):
    ws, pv = mem(); rows.append({"step": name, "s": round(time.perf_counter()-t, 3), "ws_mb": ws, "private_mb": pv})
t = time.perf_counter(); rec("bare", t)
if mode in ("full", "corpus"):
    t = time.perf_counter(); from assistant.corpus import Corpus; rec("import assistant.corpus", t)
    t = time.perf_counter(); c = Corpus(corpus_dir); rec("Corpus load", t)
    t = time.perf_counter(); c.search("한미 정상회담"); c.search("북한 비핵화", years=[2023]); pid = next(p for p,v in c.pages.items() if v["citable"]); c.read_pages([pid]); c.get_toc(2023); rec("search x2 + read + toc", t)
if mode in ("full", "gradio"):
    t = time.perf_counter(); import gradio as gr; rec("import gradio", t)
    t = time.perf_counter()
    import openai
    from openai import OpenAI
    if mode == "full":
        from assistant.llm_openai import OpenAIResponses
        llm = OpenAIResponses(OpenAI(api_key="sk-fake", base_url="https://mock.invalid/v1", max_retries=0, timeout=180))
    rec("import openai + client", t)
    t = time.perf_counter()
    for _ in range(20):
        OpenAI(api_key="sk-fake", base_url="https://mock.invalid/v1", max_retries=0, timeout=180)
    rows.append({"step": "construct OpenAI client (per run)", "ms_each": round((time.perf_counter()-t)/20*1000, 2)})
    t = time.perf_counter()
    with gr.Blocks() as demo:
        with gr.Tabs():
            for name in ["질문답변","요약","표 뽑기","비교","예시 모음"]:
                with gr.Tab(name):
                    q = gr.Textbox(); m = gr.Markdown(); d = gr.Dataframe(); gr.Button("go").click(lambda x: x, q, m)
    rec("build Blocks 5 tabs", t)
    t = time.perf_counter()
    demo.launch(server_name="127.0.0.1", server_port=int(sys.argv[4]), prevent_thread_lock=True, quiet=True, ssr_mode=False)
    import urllib.request
    urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[4]}/", timeout=10).read()
    rec("launch + GET /", t)
    demo.close()
print(json.dumps({"mode": mode, "rows": rows, "blas_threads_env": os.environ.get("OPENBLAS_NUM_THREADS")}, ensure_ascii=False))
