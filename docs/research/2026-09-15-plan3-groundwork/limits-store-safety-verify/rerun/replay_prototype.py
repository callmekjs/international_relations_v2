"""Prototype for Plan 3: example-gallery replay of a saved run record with realistic timing and no API call.

- Record v2 (proposed): every event carries "t" = seconds since the run started (see runner_timestamps.patch).
- Record v1 (today's runs/*.json): no "t"; timing is synthesised from elapsed_s so old records still replay.
- replay() is an async generator: the Gradio handler can `async for` it and yield UI updates, using
  asyncio.sleep (no worker thread held while waiting). It never imports assistant.llm_openai or openai.

Run: python replay_prototype.py <record.json> [...]   (prints only event kinds and timings, never content)
"""
from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path

VISIBLE = ("thinking", "tool_requested", "tool_finished", "tool_skipped", "answer_started", "retrying", "notice", "done")
# v1 fallback weights: how much of the run's wall time typically sits before each kind of event.
V1_WEIGHT = {"thinking": 1.0, "tool_requested": 2.0, "tool_finished": 0.3, "tool_skipped": 0.1,
             "answer_started": 2.0, "retrying": 0.5, "notice": 0.1, "done": 1.5}


def timed_events(record: dict) -> list[dict]:
    """Events with a "t" for every entry. v2 records keep theirs; v1 records get a synthetic, monotonic t."""
    events = [e for e in record.get("events", []) if e.get("event") in VISIBLE]
    if events and all(isinstance(e.get("t"), (int, float)) for e in events):
        return events
    total = float(record.get("elapsed_s") or 0) or 2.0 * max(1, len(events))
    weights = [V1_WEIGHT.get(e["event"], 1.0) for e in events]
    scale = total / (sum(weights) or 1.0)
    out, t = [], 0.0
    for event, weight in zip(events, weights):
        t += weight * scale
        out.append({**event, "t": round(t, 2), "t_synthetic": True})
    return out


def schedule(record: dict, *, speed: float = 1.0, max_gap_s: float = 6.0) -> list[tuple[float, dict]]:
    """(seconds to wait before showing the event, event). speed 2.0 = twice as fast; long silent gaps are
    capped so a replay never looks frozen (the cap is shown to the viewer as "…" in the progress line)."""
    plan, previous = [], 0.0
    for event in timed_events(record):
        gap = max(0.0, (event["t"] - previous) / speed)
        plan.append((min(gap, max_gap_s), event))
        previous = event["t"]
    return plan


async def replay(record: dict, *, speed: float = 1.0, max_gap_s: float = 6.0, sleep=asyncio.sleep):
    """Yields view states: {"progress": [event, ...], "final": record-or-None}. The final answer is taken
    from the record (the same dict the live screen renders), so replay and live use one renderer."""
    shown: list[dict] = []
    for wait, event in schedule(record, speed=speed, max_gap_s=max_gap_s):
        if wait:
            await sleep(wait)
        shown.append(event)
        yield {"progress": list(shown), "final": record if event["event"] == "done" else None}


def gallery_item(record: dict, *, slug: str, title: str, reviewed_by: str, reviewed_at: str) -> dict:
    """A frozen, reviewed copy for web/gallery/items/<slug>.json. Drops what the screen never shows."""
    keep = ("version", "task", "created_at", "prompt_version", "inputs", "model", "status", "notice",
            "events", "answer", "elapsed_s")
    item = {key: record.get(key) for key in keep}
    item["usage"] = {k: record.get("usage", {}).get(k) for k in ("turns", "tool_calls", "cost_krw")}
    item["gallery"] = {"slug": slug, "title": title, "reviewed_by": reviewed_by, "reviewed_at": reviewed_at,
                       "label": "AI 생성 · 미리 돌려 둔 실행 기록"}
    return item


class NetworkUsed(RuntimeError):
    pass


def forbid_network():
    """Refuse every non-loopback connection (the Windows asyncio loop itself uses a loopback socket pair)."""
    real_connect = socket.socket.connect

    def guarded(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise NetworkUsed(f"replay tried to open a network connection to {host}")
        return real_connect(self, address, *args, **kwargs)

    socket.socket.connect = guarded          # type: ignore[assignment]


async def _measure(path: Path) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    waits: list[float] = []

    async def fake_sleep(seconds: float):
        waits.append(round(seconds, 2))

    states = [state async for state in replay(record, sleep=fake_sleep)]
    fast: list[float] = []

    async def fake_sleep_fast(seconds: float):
        fast.append(seconds)

    [s async for s in replay(record, speed=2.0, sleep=fake_sleep_fast)]
    return {"file": path.name, "record_version": record.get("version"), "elapsed_s": record.get("elapsed_s"),
            "events": [e["event"] for e in timed_events(record)],
            "synthetic_t": any(e.get("t_synthetic") for e in timed_events(record)),
            "waits_s_speed1": waits, "replay_total_s_speed1": round(sum(waits), 2),
            "replay_total_s_speed2": round(sum(fast), 2),
            "final_state_has_answer": states[-1]["final"] is not None and states[-1]["final"].get("answer") is not None,
            "item_bytes": len(json.dumps(gallery_item(record, slug="x", title="x", reviewed_by="owner",
                                                      reviewed_at="2026-09-26"), ensure_ascii=False))}


def _demo_v2() -> dict:
    """A v2-shaped record (synthetic, no white-paper text) to show exact-t replay."""
    record = {"version": 2, "elapsed_s": 20.5, "events": [
        {"event": "tool_requested", "name": "search", "t": 3.1},
        {"event": "tool_finished", "name": "search", "summary": "찾기 …", "ok": True, "t": 3.3},
        {"event": "tool_requested", "name": "read_pages", "t": 7.9},
        {"event": "tool_finished", "name": "read_pages", "summary": "쪽 읽기 …", "ok": True, "t": 8.2},
        {"event": "thinking", "t": 12.4},
        {"event": "answer_started", "t": 14.0},
        {"event": "done", "status": "answered", "t": 20.5}], "answer": {"sentences": []}}
    waits: list[float] = []

    async def fake_sleep(seconds: float):
        waits.append(round(seconds, 2))

    async def go():
        return [s async for s in replay(record, sleep=fake_sleep)]
    asyncio.run(go())
    return {"file": "synthetic-v2", "waits_s_speed1": waits, "replay_total_s_speed1": round(sum(waits), 2)}


if __name__ == "__main__":
    forbid_network()
    before = set(sys.modules)
    results = [asyncio.run(_measure(Path(arg))) for arg in sys.argv[1:]]
    results.append(_demo_v2())
    loaded = sorted(m for m in set(sys.modules) - before if m.split(".")[0] in ("openai", "assistant", "httpx", "httpx2"))
    report = {"runs": results, "provider_modules_imported": loaded, "network_blocked": True}
    Path(__file__).with_name("replay_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                               encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))
