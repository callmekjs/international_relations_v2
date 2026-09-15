import os, sys, socket, subprocess, time, json, urllib.request
here = os.path.dirname(os.path.abspath(__file__)); py = sys.argv[1]; mode = sys.argv[2]
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}; env.update(GRADIO_ANALYTICS_ENABLED="False", HF_HUB_OFFLINE="1", PYTHONUTF8="1")
proc = subprocess.Popen([py, "-u", os.path.join(here, "server_ip.py"), str(port), mode], stdout=open(os.path.join(here, f"server_ip_{mode}.log"), "w"), stderr=subprocess.STDOUT, env=env)
out = {"mode": mode}
try:
    t0 = time.time()
    while True:
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read(); break
        except Exception:
            if time.time() - t0 > 120 or proc.poll() is not None: raise SystemExit("no server")
            time.sleep(0.3)
    from gradio_client import Client
    c = Client(f"http://127.0.0.1:{port}/", verbose=False, headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1", "X-Real-IP": "203.0.113.7", "User-Agent": "verify-ua/1.0"})
    out["whoami"] = json.loads(c.predict("x", api_name="/whoami"))
    job = c.submit("x", api_name="/gen"); out["gen_updates"] = [u for u in job]
finally:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
print(json.dumps(out, ensure_ascii=False))
