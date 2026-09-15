"""Prototype: visitor caps + daily budget that survive Space restarts on a bucket mount (topic hf-spaces).

Design choice: only CREATE-NEW-FILE writes on the mount (one small JSON per paid request), never overwrite,
append, rename or lock. That pattern works in every hf-mount write mode (streaming = sequential write,
upload on close; advanced = staged). The in-memory totals are the authority while the process lives;
at startup they are rebuilt by reading today's files. A torn/unreadable file is skipped and counted.

Assumptions (Space side): one replica, one Python process (Gradio default), so a threading.Lock is enough.
KST has no daylight saving, so a fixed +09:00 offset is exact and needs no tzdata package.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
CAPS = {"qa": 3, "summary_new": 2, "table": 1, "compare": 1}
DAILY_BUDGET_KRW = 4000


def kst_day(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(KST).strftime("%Y-%m-%d")


def visitor_key(ip: str, user_agent: str, salt: bytes) -> str:
    """HMAC with a secret salt (Space Secret), so the stored value cannot be reversed by trying all IPv4s."""
    return hmac.new(salt, f"{ip}|{user_agent}".encode("utf-8"), hashlib.sha256).hexdigest()[:32]


@dataclass
class DayTotals:
    day: str
    krw: float = 0.0
    per_visitor: dict = field(default_factory=dict)  # visitor -> {kind: count}
    unreadable_files: int = 0


class UsageLedger:
    def __init__(self, store_dir: Path, budget_krw: float = DAILY_BUDGET_KRW):
        self.dir = Path(store_dir) / "usage"
        self.budget = budget_krw
        self.lock = threading.Lock()
        self.totals = self._load(kst_day())
        self.reserved: dict[str, int] = {}

    def _load(self, day: str) -> DayTotals:
        totals = DayTotals(day)
        folder = self.dir / day
        if not folder.is_dir():
            return totals
        for path in folder.glob("*.json"):
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
                self._add(totals, event)
            except Exception:
                totals.unreadable_files += 1
        return totals

    @staticmethod
    def _add(totals: DayTotals, event: dict) -> None:
        totals.krw += float(event.get("krw", 0))
        if not event.get("presenter"):
            counts = totals.per_visitor.setdefault(event["visitor"], {})
            counts[event["kind"]] = counts.get(event["kind"], 0) + 1

    def _roll(self) -> None:
        today = kst_day()
        if self.totals.day != today:
            self.totals, self.reserved = self._load(today), {}

    def try_reserve(self, visitor: str, kind: str, presenter: bool = False) -> tuple[bool, str]:
        """Check caps before calling the model. Presenter skips caps 2 and 3 (OpenAI project limit still applies)."""
        with self.lock:
            self._roll()
            if presenter:
                return True, "presenter"
            if self.totals.krw >= self.budget:
                return False, "daily_budget"
            used = self.totals.per_visitor.get(visitor, {}).get(kind, 0) + self.reserved.get(f"{visitor}|{kind}", 0)
            if used >= CAPS[kind]:
                return False, "visitor_cap"
            self.reserved[f"{visitor}|{kind}"] = self.reserved.get(f"{visitor}|{kind}", 0) + 1
            return True, "ok"

    def record(self, visitor: str, kind: str, krw: float, presenter: bool = False) -> Path | None:
        """After the run (also after errors that cost money). Write-once file; memory updated even if the write fails."""
        event = {"visitor": visitor, "kind": kind, "krw": round(krw, 2), "presenter": presenter,
                 "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        with self.lock:
            self._roll()
            key = f"{visitor}|{kind}"
            if not presenter and self.reserved.get(key):
                self.reserved[key] -= 1
            self._add(self.totals, event)
            folder = self.dir / self.totals.day
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{event['at'].replace(':', '')}-{uuid.uuid4().hex[:8]}.json"
            path.write_text(json.dumps(event), encoding="utf-8")
            return path
        except OSError:
            return None  # log it; the in-memory totals still protect this process


if __name__ == "__main__":  # local smoke test on a temp folder
    import tempfile
    from concurrent.futures import ThreadPoolExecutor

    with tempfile.TemporaryDirectory() as tmp:
        salt = b"test-salt"
        ledger = UsageLedger(Path(tmp), budget_krw=100)
        v = visitor_key("203.0.113.7", "UA", salt)
        with ThreadPoolExecutor(8) as pool:
            grants = list(pool.map(lambda _: ledger.try_reserve(v, "qa")[0], range(10)))
        for ok in grants:
            if ok:
                ledger.record(v, "qa", 30.0)
        (Path(tmp) / "usage" / kst_day() / "torn.json").write_text('{"visitor": "x", "kin', encoding="utf-8")
        reloaded = UsageLedger(Path(tmp), budget_krw=90)  # simulates a restart; 3 x 30 KRW reaches the budget
        out = {"granted_of_10_parallel": sum(grants), "krw_after_restart": reloaded.totals.krw,
               "visitor_counts_after_restart": reloaded.totals.per_visitor.get(v),
               "unreadable_files": reloaded.totals.unreadable_files,
               "fourth_question_allowed": reloaded.try_reserve(v, "qa"),
               "other_visitor_blocked_by_budget": reloaded.try_reserve(visitor_key("198.51.100.2", "UA", salt), "qa"),
               "presenter_allowed": reloaded.try_reserve(v, "qa", presenter=True)}
        print(json.dumps(out, ensure_ascii=False))
