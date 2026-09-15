import os, sys, socket, subprocess, time, json, urllib.request
here = os.path.dirname(os.path.abspath(__file__))
py = sys.argv[1]; mode = sys.argv[2]; tag = sys.argv[3]
def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p
port = free_port()
env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
env.update(GRADIO_ANALYTICS_ENABLED="False", HF_HUB_OFFLINE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
log = open(os.path.join(here, f"server_{tag}.log"), "w", encoding="utf-8")
t0 = time.perf_counter()
proc = subprocess.Popen([py, "-u", os.path.join(here, "server.py"), str(port), mode], stdout=log, stderr=subprocess.STDOUT, env=env)
res = {"tag": tag, "mode": mode, "port": port}
try:
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                res["GET /"] = r.status; body = r.read(); break
        except Exception:
            if proc.poll() is not None: raise SystemExit("server died")
            if time.perf_counter() - t0 > 120: raise SystemExit("timeout")
            time.sleep(0.3)
    res["first_200_s"] = round(time.perf_counter() - t0, 2)
    res["root_bytes"] = len(body)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/config", timeout=5) as r:
        res["config_version"] = json.load(r).get("version")
    from gradio_client import Client
    c = Client(f"http://127.0.0.1:{port}/", verbose=False)
    t1 = time.perf_counter(); job = c.submit("2023년 질문", api_name="/ask")
    updates = [u for u in job]
    res["stream_updates"] = len(updates); res["ask_s"] = round(time.perf_counter() - t1, 2)
    res["final"] = job.result()
    res["info"] = json.loads(c.predict(api_name="/info"))
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,WorkingSetSize,PrivatePageCount | ConvertTo-Json"],
        capture_output=True, text=True)
    allp = json.loads(ps.stdout)
    tree, frontier = [], {proc.pid}
    while frontier:
        kids = [p for p in allp if p["ParentProcessId"] in frontier or p["ProcessId"] in frontier]
        new_ids = {p["ProcessId"] for p in kids} - {p["ProcessId"] for p in tree}
        tree += [p for p in kids if p["ProcessId"] in new_ids]
        frontier = new_ids
    ps = type("o", (), {"stdout": json.dumps(tree)})
    res["process_tree"] = json.loads(ps.stdout) if ps.stdout.strip() else None
finally:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    log.close()
json.dump(res, open(os.path.join(here, f"result_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
