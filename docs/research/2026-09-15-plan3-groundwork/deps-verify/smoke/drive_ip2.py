import os, sys, socket, subprocess, time, json, urllib.request
here = os.path.dirname(os.path.abspath(__file__)); py = sys.argv[1]; mode = sys.argv[2]
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}; env.update(GRADIO_ANALYTICS_ENABLED="False", HF_HUB_OFFLINE="1", PYTHONUTF8="1")
proc = subprocess.Popen([py, "-u", os.path.join(here, "server_ip.py"), str(port), mode], stdout=open(os.path.join(here, f"server_ip2_{mode}.log"), "w"), stderr=subprocess.STDOUT, env=env)
out = {"mode": mode}
try:
    t0 = time.time()
    while True:
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read(); break
        except Exception:
            if time.time() - t0 > 120 or proc.poll() is not None: raise SystemExit("no server")
            time.sleep(0.3)
    H = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 verify-browser", "X-Forwarded-For": "203.0.113.7", "Accept-Language": "ko-KR"}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/gradio_api/call/whoami", data=json.dumps({"data": ["x"]}).encode(), headers=H, method="POST")
    eid = json.load(urllib.request.urlopen(req, timeout=10))["event_id"]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/gradio_api/call/whoami/{eid}", headers=H)
    body = urllib.request.urlopen(req, timeout=30).read().decode()
    out["sse"] = body.strip()[-400:]
finally:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
print(json.dumps(out, ensure_ascii=False))
