"""Start smoke_app.py in a subprocess, wait until it serves, call it over HTTP and with gradio_client, then stop it."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from gradio_client import Client

HERE = Path(__file__).resolve().parent
import socket
_s = socket.socket(); _s.bind(("127.0.0.1", 0)); PORT = _s.getsockname()[1]; _s.close()  # free port: another app may own 7861
URL = f"http://127.0.0.1:{PORT}/"
env = {**os.environ, "PYTHONUTF8": "1", "SMOKE_PORT": str(PORT), "GRADIO_ANALYTICS_ENABLED": "False",
       "HF_HUB_DISABLE_TELEMETRY": "1", "HF_HUB_OFFLINE": "1", "NO_PROXY": "127.0.0.1,localhost"}
TAG = os.environ.get("SMOKE_TAG", "venv")
log = open(HERE / f"smoke_server_log_{TAG}.txt", "w", encoding="utf-8")
started = time.perf_counter()
proc = subprocess.Popen([sys.executable, str(HERE / "smoke_app.py")], cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT)
result = {}
try:
    for _ in range(240):
        try:
            r = httpx.get(URL, timeout=2)
            if r.status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise SystemExit(f"server exited early: {proc.returncode}")
        time.sleep(0.5)
    result["first_200_after_s"] = round(time.perf_counter() - started, 2)
    result["GET /"] = {"status": r.status_code, "bytes": len(r.content), "has_gradio": "gradio" in r.text.lower()}
    cfg = httpx.get(URL + "config", timeout=5)
    result["GET /config"] = {"status": cfg.status_code, "version": cfg.json().get("version")}
    info = httpx.get(URL + "gradio_api/info", timeout=5)
    result["GET /gradio_api/info"] = {"status": info.status_code, "endpoints": sorted(info.json().get("named_endpoints", {}))}
    c = Client(URL, verbose=False)
    t = time.perf_counter()
    job = c.submit("2023년 한미 정상회담은?", api_name="/ask")
    updates = []
    for update in job:
        updates.append(update)
    result["client /ask"] = {"final": job.result(), "streamed_updates": len(updates), "seconds": round(time.perf_counter() - t, 2)}
    result["client /info"] = c.predict(api_name="/info")
    assert result["client /info"]["openai"], "not our server"
    result["port"] = PORT
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()
print(json.dumps(result, ensure_ascii=False, indent=1))
(HERE / f"smoke_result_{TAG}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
