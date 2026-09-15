"""Adversarial checks against the researcher's limits_store.py prototype (standard library, no network)."""
from __future__ import annotations
import json, tempfile
from datetime import datetime
from pathlib import Path
import limits_store as ls

SECRET = b"k" * 32
OUT = {}

class Clock:
    def __init__(self, iso): self.t = datetime.fromisoformat(iso).timestamp()
    def __call__(self): return self.t
    def advance(self, s): self.t += s

def ids(day, ip="203.0.113.7", ua="Mozilla/5.0 Test", browser="b1"):
    return ls.visitor_ids(SECRET, day, ip, ua, "ko-KR", browser)

def leaked_tickets(root):
    """Handler admitted but never called finish (client closed tab and the generator was closed, or an
    exception before the try/finally). Nothing times the ticket out."""
    clock = Clock("2026-09-22T10:00:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    who = ids("2026-09-22", browser="leak")
    t = store.admit(who, "qa"); assert isinstance(t, ls.Ticket)
    clock.advance(6 * 3600)   # six hours later, same day
    again = store.admit(who, "qa")
    # 26 leaked visitor tickets x 150 KRW reserve block the whole day's budget without spending anything
    for i in range(26):
        store.admit(ids("2026-09-22", ip=f"198.51.100.{i}", browser=f"L{i}"), "qa")
    fresh = store.admit(ids("2026-09-22", ip="192.0.2.50", browser="fresh"), "qa")
    OUT["leak"] = {"same_visitor_6h_later": getattr(again, "kind", "admitted"),
                   "reserved_krw_after_27_leaks": store.snapshot()["reserved_krw"],
                   "visitor_spend_krw": store.snapshot()["visitor_spend_krw"],
                   "new_visitor": getattr(fresh, "kind", "admitted")}

def password_lockout_bypass(root):
    clock = Clock("2026-09-22T11:00:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    tries = 0
    for b in range(40):                        # 40 fresh browser ids (clear localStorage / incognito)
        who = ids("2026-09-22", browser=f"pw{b}")
        for _ in range(5):
            if store.check_password(who, "guess", "right-password") is False:
                tries += 1
    OUT["password_tries_from_one_ip_with_40_browser_ids"] = tries

def midnight_crossing(root):
    clock = Clock("2026-09-22T23:59:50+09:00")
    store = ls.LimitStore(root, clock=clock)
    t = store.admit(ids("2026-09-22", browser="late"), "qa")
    clock.advance(40)                          # finishes at 00:00:30 next day
    store.finish(t, status="answered", notice_kind=None, cost_krw=900, cost_usd=900/1400)
    snap = store.snapshot()
    OUT["midnight_crossing_900_krw"] = {"today_visitor_spend_krw": snap["visitor_spend_krw"],
                                        "month_visitor_krw": snap["month_visitor_krw"],
                                        "row_written_under_day": t.day}

def cap_bypass_by_browser_id(root):
    clock = Clock("2026-09-23T09:00:00+09:00")
    store = ls.LimitStore(root, clock=clock)
    admitted = 0
    for b in range(40):
        out = store.admit(ids("2026-09-23", browser=f"inc{b}"), "qa")
        if isinstance(out, ls.Ticket):
            admitted += 1
            clock.advance(11)
            store.finish(out, status="answered", notice_kind=None, cost_krw=40, cost_usd=40/1400)
    OUT["qa_runs_one_ip_one_ua_rotating_browser_id"] = admitted

def failed_turn_undercount():
    """Reads the real loop: when llm.turn raises LLMError the failed turn is never appended to turns,
    so Result.usage['cost_krw'] leaves out whatever OpenAI billed for that turn."""
    src = Path(r"C:/international_relations/assistant/loop.py").read_text(encoding="utf-8")
    i = src.find("except LLMError as exc:")
    OUT["loop_llmerror_branch"] = src[i:i+80].replace("\n", " | ")

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        leaked_tickets(root / "a"); password_lockout_bypass(root / "b"); midnight_crossing(root / "c")
        cap_bypass_by_browser_id(root / "d"); failed_turn_undercount()
    Path(__file__).with_name("adversarial_limits_results.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(OUT, ensure_ascii=False, indent=1))
