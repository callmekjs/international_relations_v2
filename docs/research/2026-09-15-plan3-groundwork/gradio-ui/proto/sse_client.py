"""Minimal raw client for Gradio's sse_v3 queue protocol (what the browser does), with arrival timestamps.

Scenarios (all against http://127.0.0.1:7861, fake model, no network beyond localhost):
  stream      one question, full run; compares client arrival times with server emit times
  disconnect  closes the SSE connection after N progress messages (tab closed) and watches the server log
  stop        sends the Stop button's cancel after N progress messages
  parallel    K questions at once from K sessions (concurrency_limit check)
  private     calls the ask endpoint by fn_index with api_visibility="private" (run the app with PROTO_API=private)
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import threading
import time
from pathlib import Path

import httpx
from gradio_client.utils import apply_diff

BASE = "http://127.0.0.1:7861"
API = BASE + "/gradio_api"
ROOT = Path(__file__).resolve().parent
LOG = ROOT / "measurements" / "server_events.jsonl"
QUESTION = "2023년 한미 정상회담은 어디서 열렸어?"


def config() -> dict:
    return httpx.get(BASE + "/config", timeout=10).json()


def dep_ids(cfg: dict) -> dict:
    ids = {}
    for d in cfg["dependencies"]:
        name = d.get("api_name") or ("cancel" if d.get("cancels") else f"dep{d['id']}")
        ids[name] = d
    return ids


def join(session: str, dep: dict, data: list, headers: dict | None = None) -> httpx.Response:
    body = {"data": data, "event_data": None, "fn_index": dep["id"], "trigger_id": dep["targets"][0][0],
            "session_hash": session}
    headers = {"User-Agent": f"probe-{session}", **(headers or {})}
    return httpx.post(API + "/queue/join", json=body, headers=headers, timeout=10)


def _plain(value, old):
    if isinstance(value, dict) and value.get("__type__") == "update":
        return value.get("value", old)
    return value


def _merge(old, diff):
    """One output of a process_generating message: [] = unchanged, else a list of [action, path, value]."""
    if diff is None or diff == []:
        return old
    if isinstance(diff, list) and all(isinstance(op, list) and len(op) == 3 for op in diff):
        return _plain(apply_diff(old, diff), old)
    return _plain(diff, old)


def last_line(html: str) -> str:
    items = re.findall(r"<li[^>]*>(.*?)</li>", html or "")
    return items[-1] if items else ""


def listen(session: str, *, stop_after: int | None = None, on_count=None, out: list | None = None,
           headers: dict | None = None) -> list[dict]:
    """Reads the SSE stream; returns one row per message with arrival time and the reconstructed outputs."""
    rows = out if out is not None else []
    state: list | None = None
    progress_msgs = 0
    with httpx.stream("GET", API + "/queue/data", params={"session_hash": session}, headers=headers or {},
                      timeout=httpx.Timeout(60, read=60)) as resp:
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            t = time.time()
            msg = json.loads(line[5:])
            kind = msg.get("msg")
            row = {"t": t, "msg": kind}
            if kind in ("process_generating", "process_completed") and msg.get("output", {}).get("data") is not None:
                data = msg["output"]["data"]
                if state is None:
                    state = [_plain(v, None) for v in data]
                elif kind == "process_generating":
                    state = [_merge(old, diff) for old, diff in zip(state, data)]
                else:
                    state = [_plain(v, old) for old, v in zip(state, data)]
                progress = state[0] if state and isinstance(state[0], str) else ""
                row.update(n_lines=progress.count("<li"), last=last_line(progress),
                           running="진행 중" in progress, answer_len=len(state[1] or "") if isinstance(state[1], str) else None)
                if kind == "process_generating":
                    progress_msgs += 1
            if kind == "process_completed":
                row["success"] = msg.get("success")
            rows.append(row)
            if on_count is not None:
                on_count(progress_msgs)
            if stop_after is not None and progress_msgs >= stop_after:
                row["client_closed"] = True
                return rows
            if kind == "process_completed" or kind == "close_stream":
                if kind == "process_completed":
                    return rows
    return rows


def server_rows(since: float) -> list[dict]:
    if not LOG.is_file():
        return []
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if r["t"] >= since]


def scenario_stream(args) -> dict:
    cfg = dep_ids(config())
    session = secrets.token_hex(6)
    t0 = time.time()
    join(session, cfg["ask"], [QUESTION, ["2023"], None],
         headers={"X-Forwarded-For": "203.0.113.7, 198.51.100.2", "User-Agent": "sse-probe/1.0"}).raise_for_status()
    rows = listen(session)
    srv = server_rows(t0)
    run_ids = [r["run"] for r in srv if r.get("what") == "emit"]
    run_id = run_ids[0] if run_ids else None
    emits = [r for r in srv if r.get("run") == run_id and r.get("what") == "emit"]
    shown_kinds = {"thinking", "tool_requested", "tool_finished", "tool_skipped", "answer_started", "retrying"}
    shown = [r for r in emits if r["kind"] in shown_kinds]
    # client messages that changed the line list (ignore ticks: same last line)
    changes, prev = [], None
    for r in rows:
        if r["msg"] == "process_generating" and "last" in r and (r["n_lines"], r["last"]) != prev:
            if r["n_lines"] > 0:
                changes.append(r)
            prev = (r["n_lines"], r["last"])
    pairs = []
    for e, c in zip(shown, changes):
        pairs.append({"kind": e["kind"], "emit_s": round(e["t"] - t0, 3), "arrive_s": round(c["t"] - t0, 3),
                      "lag_ms": round((c["t"] - e["t"]) * 1000, 1), "client_last_line": c["last"][:60]})
    completed = [r for r in rows if r["msg"] == "process_completed"]
    request_row = next((r for r in srv if r.get("what") == "request"), {})
    return {"scenario": "stream", "session": session, "run": run_id, "events_emitted": [e["kind"] for e in emits],
            "shown_events": len(shown), "client_line_changes": len(changes), "pairs": pairs,
            "max_lag_ms": max((p["lag_ms"] for p in pairs), default=None),
            "in_order": [p["kind"] for p in pairs] == [e["kind"] for e in shown[:len(pairs)]]
                        and all(pairs[i]["arrive_s"] <= pairs[i + 1]["arrive_s"] for i in range(len(pairs) - 1)),
            "total_messages": len(rows), "tick_messages": sum(1 for r in rows if r["msg"] == "process_generating") - len(changes),
            "completed_s": round(completed[0]["t"] - t0, 3) if completed else None,
            "server_saw": {k: request_row.get(k) for k in ("client_host", "xff_chain", "headers")}}


def scenario_interrupt(args, mode: str) -> dict:
    cfg = dep_ids(config())
    session = secrets.token_hex(6)
    t0 = time.time()
    event_id = join(session, cfg["ask"], [QUESTION, ["2023"], None]).json()["event_id"]
    rows: list[dict] = []
    if mode == "disconnect":
        listen(session, stop_after=args.after, out=rows)
        t_cut = time.time()
    else:
        t_cut = None

        def press_stop():
            stop_dep = cfg["stop"]
            if args.how in ("both", "stopfn"):   # the stop button's own fn (queue=False)
                httpx.post(API + "/run/predict", json={"data": [], "event_data": None, "fn_index": stop_dep["id"],
                                                       "trigger_id": stop_dep["targets"][0][0],
                                                       "session_hash": session}, timeout=10)
            if args.how in ("both", "cancel"):   # what cancels=[ask_event] makes the browser send
                httpx.post(API + "/cancel", json={"session_hash": session, "fn_index": cfg["ask"]["id"],
                                                  "event_id": event_id}, timeout=10)

        def trigger(count):
            nonlocal t_cut
            if t_cut is None and count >= args.after:
                t_cut = time.time()
                threading.Thread(target=press_stop, daemon=True).start()
        listen(session, on_count=trigger, out=rows)
    completed = [r for r in rows if r["msg"] == "process_completed"]
    # watch the server for a while
    deadline = time.time() + args.watch
    run_id, ended = None, None
    while time.time() < deadline:
        srv = server_rows(t0)
        emits = [r for r in srv if r.get("what") == "emit"]
        run_id = run_id or (emits[0]["run"] if emits else None)
        ended = next((r for r in srv if r.get("run") == run_id and r.get("what") in ("run_returned", "crash")), None)
        if ended:
            break
        time.sleep(0.25)
    srv = [r for r in server_rows(t0) if r.get("run") in (run_id, None)]
    timeline = [{"s": round(r["t"] - t0, 3), "where": r.get("where"), "what": r.get("what"), "kind": r.get("kind"),
                 "reason": r.get("reason"), "status": r.get("status")} for r in srv
                if r.get("what") in ("emit", "cancel_raised", "closed", "run_returned", "crash", "stop_clicked", "unload", "yield")]
    return {"scenario": mode, "how": args.how if mode == "stop" else None, "after_progress_msgs": args.after,
            "client_completed_s": round(completed[0]["t"] - t0, 3) if completed else None, "cut_s": round(t_cut - t0, 3) if t_cut else None,
            "run": run_id, "ended": ended and {"s": round(ended["t"] - t0, 3), "status": ended.get("status"),
                                                 "notice": ended.get("notice"), "reason": ended.get("reason")},
            "emits_after_cut": sum(1 for r in srv if r.get("what") == "emit" and t_cut and r["t"] > t_cut),
            "timeline": timeline}


def scenario_parallel(args) -> dict:
    cfg = dep_ids(config())
    t0 = time.time()
    results = {}

    def one(i):
        session = secrets.token_hex(6)
        join(session, cfg["ask"], [QUESTION, ["2023"], None],
             headers={"User-Agent": f"parallel-{i}"}).raise_for_status()
        rows = listen(session)
        est = [r for r in rows if r["msg"] == "estimation"]
        starts = [r for r in rows if r["msg"] == "process_starts"]
        done = [r for r in rows if r["msg"] == "process_completed"]
        results[i] = {"start_s": round(starts[0]["t"] - t0, 2) if starts else None,
                      "done_s": round(done[0]["t"] - t0, 2) if done else None, "estimation_msgs": len(est)}

    threads = [threading.Thread(target=one, args=(i,)) for i in range(args.k)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return {"scenario": "parallel", "k": args.k, "sessions": dict(sorted(results.items()))}


def scenario_private(args) -> dict:
    cfg = config()
    ask = next(d for d in cfg["dependencies"] if d.get("api_name") == "ask")
    session = secrets.token_hex(6)
    r = join(session, ask, [QUESTION, ["2023"], None])
    out = {"scenario": "private", "api_visibility": ask.get("api_visibility"), "join_status": r.status_code,
           "join_body": r.text[:200]}
    if r.status_code == 200:
        rows = listen(session)
        out["completed"] = any(x["msg"] == "process_completed" and x.get("success") for x in rows)
    info = httpx.get(API + "/info", timeout=10).json()
    out["listed_in_api_info"] = "/ask" in info.get("named_endpoints", {})
    try:
        from gradio_client import Client
        Client(BASE, verbose=False).predict(QUESTION, ["2023"], api_name="/ask")
        out["gradio_client_predict"] = "worked"
    except Exception as exc:  # noqa: BLE001
        out["gradio_client_predict"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("scenario", choices=["stream", "disconnect", "stop", "parallel", "private"])
    p.add_argument("--after", type=int, default=4)
    p.add_argument("--watch", type=float, default=20)
    p.add_argument("--k", type=int, default=6)
    p.add_argument("--how", choices=["both", "stopfn", "cancel"], default="both")
    a = p.parse_args()
    if a.scenario == "stream":
        res = scenario_stream(a)
    elif a.scenario in ("disconnect", "stop"):
        res = scenario_interrupt(a, a.scenario)
    elif a.scenario == "parallel":
        res = scenario_parallel(a)
    else:
        res = scenario_private(a)
    print(json.dumps(res, ensure_ascii=False, indent=1))
