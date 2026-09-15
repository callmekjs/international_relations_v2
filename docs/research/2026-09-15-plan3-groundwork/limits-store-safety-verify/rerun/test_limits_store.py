"""Checks for limits_store.py. Run: python test_limits_store.py  (standard library only, no network)."""
from __future__ import annotations

import json
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import limits_store as ls

SECRET = b"k" * 32
RESULTS: dict = {}


class Clock:
    def __init__(self, iso: str):
        self.t = datetime.fromisoformat(iso).timestamp()

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def ids(day: str, ip="203.0.113.7", ua="Mozilla/5.0 Test", browser="b1"):
    return ls.visitor_ids(SECRET, day, ip, ua, "ko-KR", browser)


def run(store, who, task="qa", cost=40, presenter=False, status="answered", notice=None, clock=None):
    ticket = store.admit(who, task, presenter=presenter)
    if isinstance(ticket, ls.Refusal):
        return ticket
    if clock:
        clock.advance(12)
    store.finish(ticket, status=status, notice_kind=notice, cost_krw=cost, cost_usd=cost / 1400)
    return ticket


def test_visitor_cap_and_kst_rollover(root: Path):
    clock = Clock("2026-09-20T23:58:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    who = ids("2026-09-20")
    for _ in range(3):
        assert isinstance(run(store, who, clock=clock), ls.Ticket)
    refusal = run(store, who, clock=clock)
    assert isinstance(refusal, ls.Refusal) and refusal.kind == "visitor_cap", refusal
    assert refusal.retry_at == "2026-09-21T00:00+09:00", refusal.retry_at
    clock.t = datetime.fromisoformat("2026-09-21T00:00:01+09:00").timestamp()  # = 2026-09-20T15:00:01Z
    who_next_day = ids("2026-09-21")  # the web layer recomputes ids with the new KST day
    assert isinstance(run(store, who_next_day, clock=clock), ls.Ticket)
    RESULTS["visitor_cap_rollover"] = "4th question refused until 2026-09-21T00:00+09:00; allowed at 00:00:01 KST"


def test_min_interval_and_inflight(root: Path):
    clock = Clock("2026-09-20T10:00:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    who = ids("2026-09-20", browser="b2")
    first = store.admit(who, "qa")
    assert isinstance(first, ls.Ticket)
    clock.advance(30)
    second = store.admit(who, "qa")
    assert isinstance(second, ls.Refusal) and second.kind == "busy_visitor"
    store.finish(first, status="answered", notice_kind=None, cost_krw=30, cost_usd=0.02)
    third = store.admit(who, "qa")
    assert isinstance(third, ls.Ticket)
    store.finish(third, status="answered", notice_kind=None, cost_krw=30, cost_usd=0.02)
    clock.advance(3)
    fourth = store.admit(who, "qa")
    assert isinstance(fourth, ls.Refusal) and fourth.kind == "too_soon", fourth
    RESULTS["inflight_interval"] = "second start while running -> busy_visitor; start 3 s after -> too_soon"


def test_refund_on_no_output_error(root: Path):
    clock = Clock("2026-09-20T11:00:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    who = ids("2026-09-20", browser="b3")
    for _ in range(3):
        run(store, who, cost=0, status="error", notice="busy", clock=clock)
    assert store.remaining(who)["qa"] == 3
    run(store, who, cost=25, status="partial", notice="stream_broken", clock=clock)
    assert store.remaining(who)["qa"] == 2
    RESULTS["refund"] = "3 x busy errors (0 KRW) refunded; a cut stream that cost 25 KRW is counted"


def test_global_stop_presenter_and_restart(root: Path):
    clock = Clock("2026-09-22T09:00:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    n = 0
    while True:
        who = ids("2026-09-22", ip=f"198.51.100.{n % 250}", browser=f"g{n}")
        outcome = run(store, who, cost=300, clock=clock)
        if isinstance(outcome, ls.Refusal):
            assert outcome.kind == "daily_stop", outcome
            break
        n += 1
    snap = store.snapshot()
    assert snap["visitor_spend_krw"] + ls.RESERVE_KRW["qa"] > ls.DAILY_STOP_KRW
    presenter = ids("2026-09-22", browser="presenter")
    assert isinstance(run(store, presenter, cost=500, presenter=True, clock=clock), ls.Ticket)
    restarted = ls.LimitStore(root, clock=clock)  # a Space restart: counters come back from the ledger
    snap2 = restarted.snapshot()
    assert snap2["visitor_spend_krw"] == snap["visitor_spend_krw"], (snap, snap2)
    assert snap2["presenter_spend_krw"] == 500
    blocked = run(restarted, ids("2026-09-22", ip="192.0.2.99", browser="late"), cost=10, clock=clock)
    assert isinstance(blocked, ls.Refusal) and blocked.kind == "daily_stop"
    RESULTS["global_stop"] = (f"{n} visitor runs of 300 KRW admitted (spent {snap['visitor_spend_krw']} KRW), "
                              f"next refused; presenter still allowed; restart restored spend={snap2['visitor_spend_krw']} "
                              f"presenter={snap2['presenter_spend_krw']}")


def test_concurrency(root: Path):
    clock = Clock("2026-09-23T12:00:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    admitted: list = []
    barrier = threading.Barrier(64)

    def same_visitor():
        barrier.wait()
        outcome = store.admit(ids("2026-09-23", browser="same"), "qa")
        if isinstance(outcome, ls.Ticket):
            admitted.append(outcome)

    threads = [threading.Thread(target=same_visitor) for _ in range(64)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(admitted) == 1, len(admitted)

    admitted.clear()
    barrier = threading.Barrier(200)

    def many_visitors(i: int):
        barrier.wait()
        outcome = store.admit(ids("2026-09-23", ip=f"198.18.{i // 250}.{i % 250}", browser=f"c{i}"), "qa")
        if isinstance(outcome, ls.Ticket):
            admitted.append(outcome)

    threads = [threading.Thread(target=many_visitors, args=(i,)) for i in range(200)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    reserved = store.snapshot()["reserved_krw"]
    assert reserved <= ls.DAILY_STOP_KRW, reserved
    RESULTS["concurrency"] = (f"64 simultaneous starts by one visitor -> 1 admitted; 200 simultaneous visitors -> "
                              f"{len(admitted)} admitted, reserved {reserved} KRW <= {ls.DAILY_STOP_KRW} "
                              f"(one earlier visitor still in flight)")


def test_ip_cap_and_password(root: Path):
    clock = Clock("2026-09-24T12:00:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    refused = None
    for i in range(ls.IP_DAILY_RUNS + 1):
        outcome = run(store, ids("2026-09-24", ip="203.0.113.50", browser=f"incognito{i}"), cost=20, clock=clock)
        if isinstance(outcome, ls.Refusal):
            refused = (i, outcome.kind)
    assert refused == (ls.IP_DAILY_RUNS, "ip_cap"), refused
    who = ids("2026-09-24", browser="pw")
    results = [store.check_password(who, "wrong", "right-password") for _ in range(6)]
    assert results == [False] * 5 + [None], results
    RESULTS["ip_cap_password"] = (f"{ls.IP_DAILY_RUNS} runs from one IP with fresh browser ids, the next refused (ip_cap); "
                                  "5 wrong passwords then locked for the day")


def test_ledger_privacy(root: Path):
    raw_ip, raw_ua = "203.0.113.7", "Mozilla/5.0 Test"
    for path in (root / "usage").rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert raw_ip not in text and raw_ua not in text and "ko-KR" not in text
    sample = json.loads(next((root / "usage").rglob("*.json")).read_text(encoding="utf-8"))
    RESULTS["ledger_row_example"] = sample
    RESULTS["ledger_row_bytes"] = len(json.dumps(sample, ensure_ascii=False, separators=(",", ":")))


def test_ip_rules():
    assert ls.normalize_ip("2001:db8:1234:5678:aaaa:bbbb:cccc:dddd") == "2001:db8:1234:5678::/64"
    assert ls.normalize_ip("::ffff:203.0.113.9") == "203.0.113.9"
    assert ls.pick_client_ip({"x-forwarded-for": "1.2.3.4, 8.8.8.8, 10.0.0.2"}, "10.0.0.3") == "8.8.8.8"
    assert ls.pick_client_ip({}, "8.8.4.4") == "8.8.4.4"
    safety = ids("2026-09-20").safety
    assert len(safety) == 64 and safety == ids("2026-09-21").safety   # stable across days
    assert ids("2026-09-20").visitor != ids("2026-09-21").visitor         # counting key rotates daily
    RESULTS["ip_rules"] = "IPv6 -> /64, mapped IPv4 unwrapped, XFF last public entry, safety id 64 hex stable, visitor key rotates"


def test_rebuild_speed(root: Path):
    clock = Clock("2026-09-25T12:00:00+09:00")
    day_dir = root / "usage" / "2026-09-25"
    for i in range(2000):
        ls.write_once(day_dir / f"20260925T120000-{i:08x}.json",
                      {"v": 1, "day": "2026-09-25", "task": "qa", "visitor": f"{i:016x}", "ip": f"{i % 97:016x}",
                       "presenter": False, "refunded": False, "cost_krw": 1})
    start = time.perf_counter()
    store = ls.LimitStore(root, clock=clock)
    elapsed = time.perf_counter() - start
    assert store.snapshot()["visitor_spend_krw"] == 2000
    RESULTS["rebuild_2000_files_local_disk_s"] = round(elapsed, 3)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        test_ip_rules()
        test_visitor_cap_and_kst_rollover(root / "a")
        test_min_interval_and_inflight(root / "b")
        test_refund_on_no_output_error(root / "c")
        test_global_stop_presenter_and_restart(root / "d")
        test_concurrency(root / "e")
        test_ip_cap_and_password(root / "f")
        test_ledger_privacy(root / "d")
        test_rebuild_speed(root / "g")
    out = Path(__file__).with_name("limits_store_results.json")
    out.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(RESULTS, ensure_ascii=False, indent=1))
    print("ALL PASSED")


def test_month_summaries(root: Path):
    """30 past days x 150 runs: first start builds one summary per day, second start reads only summaries."""
    for day in range(1, 31):
        name = f"2026-09-{day:02d}"
        if name >= "2026-09-30":
            break
        for i in range(150):
            ls.write_once(root / "usage" / name / f"r-{i:04d}.json",
                          {"v": 1, "day": name, "task": "qa", "visitor": f"{i:016x}", "ip": "x",
                           "presenter": False, "refunded": False, "cost_krw": 2})
    clock = Clock("2026-09-30T08:00:00+09:00")
    t0 = time.perf_counter(); first = ls.LimitStore(root, clock=clock); t1 = time.perf_counter()
    second = ls.LimitStore(root, clock=clock); t2 = time.perf_counter()
    assert first.snapshot()["month_visitor_krw"] == second.snapshot()["month_visitor_krw"] == 29 * 150 * 2
    RESULTS["month_rebuild"] = {"files": 29 * 150, "first_start_s": round(t1 - t0, 2),
                                "second_start_with_day_summaries_s": round(t2 - t1, 3)}


if __name__ == "__main__":  # second block: month rebuild timing
    with tempfile.TemporaryDirectory() as tmp:
        test_month_summaries(Path(tmp))
    out = Path(__file__).with_name("limits_store_results.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    data["month_rebuild"] = RESULTS["month_rebuild"]
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(RESULTS["month_rebuild"])
