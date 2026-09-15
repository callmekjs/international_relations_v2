"""Headless checks against the running prototype (127.0.0.1:7861): presenter unlock kept in server-side
gr.State for one session only, per-visitor cap, CSV download bytes, monitoring and API routes."""
from __future__ import annotations

import json
import secrets
import sys

import httpx

import sse_client as s


def call(session: str, name: str, data: list, headers: dict | None = None) -> list[dict]:
    deps = s.dep_ids(s.config())
    s.join(session, deps[name], data, headers=headers).raise_for_status()
    rows: list[dict] = []
    final = None
    with httpx.stream("GET", s.API + "/queue/data", params={"session_hash": session}, timeout=60) as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                msg = json.loads(line[5:])
                if msg.get("msg") == "process_completed":
                    final = msg
                    break
    return final


def main() -> dict:
    out: dict = {}
    ua = {"User-Agent": "misc-probe-A"}
    # 1. wrong password x2, then the right one, in session A; then ask in A (unlocked) and in B (same visitor, locked)
    a, b = secrets.token_hex(6), secrets.token_hex(6)
    wrong = [call(a, "unlock", ["nope", None], ua)["output"]["data"][1] for _ in range(2)]
    right = call(a, "unlock", ["demo-pass", None], ua)["output"]["data"][1]
    out["unlock_messages"] = {"wrong": wrong, "right": right}
    ask_a = call(a, "ask", [s.QUESTION, ["2023"], None], ua)["output"]["data"][3]
    ask_b = [call(b, "ask", [s.QUESTION, ["2023"], None], ua)["output"]["data"][3] for _ in range(4)]
    out["remaining_after_unlock_same_session"] = ask_a
    out["remaining_other_session_same_visitor"] = ask_b
    # 2. brute force lock-out: 5 wrong answers from one visitor, then even the right one is refused
    c = secrets.token_hex(6)
    ua_c = {"User-Agent": "misc-probe-C"}
    for _ in range(5):
        call(c, "unlock", ["guess", None], ua_c)
    out["after_5_fails_right_password"] = call(c, "unlock", ["demo-pass", None], ua_c)["output"]["data"][1]
    # 3. CSV download
    d = secrets.token_hex(6)
    done = call(d, "make_csv", [], ua)
    value = done["output"]["data"][0]
    file_info = value.get("value", value) if isinstance(value, dict) else value
    url = file_info.get("url") if isinstance(file_info, dict) else None
    out["csv_output"] = {k: file_info.get(k) for k in ("path", "url", "orig_name", "mime_type", "size")} if isinstance(file_info, dict) else file_info
    if url:
        r = httpx.get(url if url.startswith("http") else s.BASE + url, timeout=10)
        out["csv_download"] = {"status": r.status_code, "first_bytes_hex": r.content[:3].hex(),
                               "content_type": r.headers.get("content-type"),
                               "content_disposition": r.headers.get("content-disposition"),
                               "text": r.content.decode("utf-8-sig")[:60]}
    # 4. routes a visitor could poke
    for path in ("/gradio_api/info", "/gradio_api/monitoring", "/monitoring/summary", "/gradio_api/monitoring/summary",
                 "/gradio_api/runs", "/gradio_api/openapi.json", "/gradio_api/mcp/schema"):
        r = httpx.get(s.BASE + path, timeout=10)
        out.setdefault("routes", {})[path] = {"status": r.status_code, "body": r.text[:120]}
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(main(), ensure_ascii=False, indent=1))
