"""Prototype for Plan 3: visitor keys, per-visitor daily caps, global daily KRW stop, presenter bypass,
and a restart-safe usage ledger. Standard library only. NOT app code; a sketch to measure and test.

Design (see report.md section 1):
- Day = KST calendar day. Korea has no DST, so a fixed +09:00 offset is exact and needs no tzdata.
- visitor key  = HMAC(secret, "v|day|ip|ua|lang|browser_id")  -> 64 hex, changes every KST day
- ip key       = HMAC(secret, "i|day|ip")                       -> per-IP soft cap (incognito loops)
- safety id    = HMAC(secret, "s|ip|ua")                         -> stable 64 hex for OpenAI safety_identifier
  Raw IP / user agent are never written anywhere.
- State: in memory (guarded by one threading.Lock) + one small JSON file per finished run under
  <root>/usage/<YYYY-MM-DD>/ . Files are only ever created and closed once (no append, no rename, no
  in-place edit), which suits a bucket volume mount whose default write mode is append-only upload-on-close.
- Startup rebuilds today's counters (and this month's spend) by reading those files.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

KST = timezone(timedelta(hours=9), "KST")

VISITOR_CAPS = {"qa": 3, "summary_new": 2, "table": 1, "compare": 1}   # decided by the user (spec 6.3)
DAILY_STOP_KRW = 4000                                                  # decided (spec 6.3)
MONTHLY_VISITOR_STOP_KRW = 12_600   # proposal: visitors stop at about $9 so the presenter keeps headroom under $12
RESERVE_KRW = {"qa": 150, "summary_new": 600, "table": 1000, "compare": 1000}  # proposal: typical-high estimate
IP_DAILY_RUNS = 30                  # proposal: soft cap per IP whatever the browser (venue Wi-Fi shares one IP)
MIN_INTERVAL_S = 10.0               # proposal: seconds between two starts by the same visitor
MAX_INFLIGHT_PER_VISITOR = 1
PASSWORD_FAILS_PER_DAY = 5
# Runs that ended before the model produced anything the visitor could use give the slot back.
REFUND_NOTICES = frozenset({"busy", "server_error", "timeout", "connection", "config_error", "budget",
                            "bad_request", "unknown"})


def kst_now(clock: Callable[[], float] = time.time) -> datetime:
    return datetime.fromtimestamp(clock(), KST)


def next_kst_midnight(now: datetime) -> datetime:
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def normalize_ip(raw: str) -> str:
    """IPv4 as is; IPv6 cut to its /64 (one household or phone usually owns a whole /64)."""
    raw = (raw or "").strip().strip("[]")
    try:
        ip = ipaddress.ip_address(raw.split("%")[0])
    except ValueError:
        return "unknown"
    if ip.version == 6 and ip.ipv4_mapped:
        return str(ip.ipv4_mapped)
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address) + "/64"
    return str(ip)


def pick_client_ip(headers: dict[str, str], client_host: str | None) -> str:
    """Placeholder rule until the first deploy shows what the Hugging Face proxy sends (report 1.2):
    prefer client.host when it is a public address (uvicorn already applied X-Forwarded-For from a
    trusted proxy), else the LAST public address in X-Forwarded-For (the entry the proxy appended;
    the first entries can be typed by the visitor)."""
    def public(value: str) -> bool:
        try:
            ip = ipaddress.ip_address(value.strip().strip("[]"))
        except ValueError:
            return False
        return ip.is_global
    if client_host and public(client_host):
        return client_host
    forwarded = [part.strip() for part in (headers.get("x-forwarded-for") or "").split(",") if part.strip()]
    for value in reversed(forwarded):
        if public(value):
            return value
    return client_host or "unknown"


def _mac(secret: bytes, text: str) -> str:
    return hmac.new(secret, text.encode("utf-8"), hashlib.sha256).hexdigest()  # 64 hex characters


@dataclass(frozen=True)
class VisitorIds:
    visitor: str        # per KST day
    ip: str             # per KST day
    safety: str         # stable, sent to OpenAI as safety_identifier (max 64 characters)


def visitor_ids(secret: bytes, day: str, ip: str, user_agent: str, accept_language: str = "",
                browser_id: str = "") -> VisitorIds:
    ip_n = normalize_ip(ip)
    ua = (user_agent or "")[:300]
    lang = (accept_language or "")[:100]
    return VisitorIds(visitor=_mac(secret, f"v|{day}|{ip_n}|{ua}|{lang}|{browser_id[:64]}"),
                      ip=_mac(secret, f"i|{day}|{ip_n}"),
                      safety=_mac(secret, f"s|{ip_n}|{ua}"))


@dataclass(frozen=True)
class Refusal:
    kind: str            # visitor_cap | ip_cap | too_soon | busy_visitor | daily_stop | monthly_stop
    message: str
    retry_at: str | None = None


@dataclass
class Ticket:
    id: str
    day: str
    task: str
    visitor: str
    ip: str
    presenter: bool
    reserve_krw: int
    started: float


@dataclass
class DayState:
    day: str
    visitor_counts: dict = field(default_factory=dict)   # (visitor, task) -> n
    ip_runs: dict = field(default_factory=dict)          # ip -> n
    visitor_spend_krw: int = 0
    presenter_spend_krw: int = 0
    reserved_krw: int = 0
    inflight: dict = field(default_factory=dict)         # visitor -> n
    last_start: dict = field(default_factory=dict)       # visitor -> epoch seconds
    password_fails: dict = field(default_factory=dict)   # visitor -> n


class LimitStore:
    def __init__(self, root: Path, *, clock: Callable[[], float] = time.time,
                 writer: Callable[[Path, dict], None] | None = None):
        self.root = Path(root)
        self.clock = clock
        self._write = writer or write_once
        self._lock = threading.Lock()
        self._state = DayState(kst_now(clock).strftime("%Y-%m-%d"))
        self._month_visitor_krw = 0
        self._month = self._state.day[:7]
        self.rebuild()

    # ---- startup ----------------------------------------------------------------------------
    def rebuild(self) -> None:
        """Recount today's caps from today's ledger files, and this month's visitor spend from one summary file
        per finished day (written here the first time a past day is seen, so later restarts read 1 file per day)."""
        today = kst_now(self.clock).strftime("%Y-%m-%d")
        state = DayState(today)
        month_krw = 0
        usage = self.root / "usage"
        summaries = usage / "_days"
        if usage.is_dir():
            for day_dir in sorted(usage.iterdir()):
                name = day_dir.name
                if name == "_days" or not name.startswith(today[:7]):
                    continue
                if name == today:
                    for row in _rows(day_dir):
                        _apply(state, row)
                    continue
                summary_path = summaries / f"{name}.json"
                try:
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    past = DayState(name)
                    for row in _rows(day_dir):
                        _apply(past, row)
                    summary = {"v": 1, "day": name, "visitor_spend_krw": past.visitor_spend_krw,
                               "presenter_spend_krw": past.presenter_spend_krw, "runs": sum(past.visitor_counts.values())}
                    try:
                        self._write(summary_path, summary)
                    except OSError:
                        pass  # another start wrote it first, or the volume is read-only: recount next time
                month_krw += int(summary.get("visitor_spend_krw", 0))
        month_krw += state.visitor_spend_krw
        with self._lock:
            self._state, self._month_visitor_krw, self._month = state, month_krw, today[:7]

    def _roll_day(self) -> DayState:
        today = kst_now(self.clock).strftime("%Y-%m-%d")
        if today != self._state.day:
            carry_reserved = self._state.reserved_krw  # runs still going keep their reservation
            self._state = DayState(today, reserved_krw=carry_reserved)
            if today[:7] != self._month:
                self._month, self._month_visitor_krw = today[:7], 0
        return self._state

    # ---- before a run -----------------------------------------------------------------------
    def admit(self, ids: VisitorIds, task: str, *, presenter: bool = False) -> Ticket | Refusal:
        now = self.clock()
        vk, ik = ids.visitor[:16], ids.ip[:16]   # same keys the ledger rows store
        with self._lock:
            s = self._roll_day()
            retry = next_kst_midnight(kst_now(self.clock)).isoformat(timespec="minutes")
            reserve = RESERVE_KRW[task]
            if not presenter:
                if s.inflight.get(vk, 0) >= MAX_INFLIGHT_PER_VISITOR:
                    return Refusal("busy_visitor", "앞의 요청이 끝난 뒤 다시 해 주세요.")
                if now - s.last_start.get(vk, -1e9) < MIN_INTERVAL_S:
                    return Refusal("too_soon", "잠시 뒤 다시 해 주세요.")
                if s.visitor_counts.get((vk, task), 0) >= VISITOR_CAPS[task]:
                    return Refusal("visitor_cap", "오늘 쓸 수 있는 횟수를 다 썼어요. 예시 모음은 계속 볼 수 있어요.", retry)
                if s.ip_runs.get(ik, 0) >= IP_DAILY_RUNS:
                    return Refusal("ip_cap", "이 네트워크에서 오늘 쓸 수 있는 횟수를 다 썼어요.", retry)
                if s.visitor_spend_krw + s.reserved_krw + reserve > DAILY_STOP_KRW:
                    return Refusal("daily_stop", "오늘 전체 사용량이 다 찼어요. 예시 모음은 계속 볼 수 있어요.", retry)
                if self._month_visitor_krw + s.reserved_krw + reserve > MONTHLY_VISITOR_STOP_KRW:
                    return Refusal("monthly_stop", "이번 달 사용량이 다 찼어요. 예시 모음은 계속 볼 수 있어요.")
                s.visitor_counts[(vk, task)] = s.visitor_counts.get((vk, task), 0) + 1
                s.ip_runs[ik] = s.ip_runs.get(ik, 0) + 1
                s.reserved_krw += reserve
                s.last_start[vk] = now
            s.inflight[vk] = s.inflight.get(vk, 0) + 1
            return Ticket(secrets.token_hex(4), s.day, task, vk, ik, presenter,
                          0 if presenter else reserve, now)

    # ---- after a run ------------------------------------------------------------------------
    def finish(self, ticket: Ticket, *, status: str, notice_kind: str | None, cost_krw: int, cost_usd: float,
               extra: dict | None = None) -> dict:
        refunded = (not ticket.presenter and cost_krw == 0 and status in ("error", "partial")
                    and notice_kind in REFUND_NOTICES)
        with self._lock:
            s = self._roll_day()
            s.reserved_krw = max(0, s.reserved_krw - ticket.reserve_krw)
            s.inflight[ticket.visitor] = max(0, s.inflight.get(ticket.visitor, 0) - 1)
            same_day = ticket.day == s.day
            if refunded and same_day:
                key = (ticket.visitor, ticket.task)
                s.visitor_counts[key] = max(0, s.visitor_counts.get(key, 0) - 1)
                s.ip_runs[ticket.ip] = max(0, s.ip_runs.get(ticket.ip, 0) - 1)
            if ticket.presenter:
                s.presenter_spend_krw += cost_krw if same_day else 0
            else:
                s.visitor_spend_krw += cost_krw if same_day else 0
                self._month_visitor_krw += cost_krw
        started = datetime.fromtimestamp(ticket.started, KST)
        row = {"v": 1, "id": ticket.id, "day": ticket.day, "started_kst": started.isoformat(timespec="seconds"),
               "task": ticket.task, "visitor": ticket.visitor, "ip": ticket.ip,
               "presenter": ticket.presenter, "status": status, "notice": notice_kind, "refunded": refunded,
               "cost_krw": cost_krw, "cost_usd": round(cost_usd, 6),
               "elapsed_s": round(self.clock() - ticket.started, 2), **(extra or {})}
        path = self.root / "usage" / ticket.day / f"{started.strftime('%Y%m%dT%H%M%S')}-{ticket.id}.json"
        self._write(path, row)   # outside the lock: an upload-on-close mount can take a while
        return row

    # ---- presenter password -----------------------------------------------------------------
    def check_password(self, ids: VisitorIds, typed: str, expected: str) -> bool | None:
        """True / False, or None when this visitor has used up today's attempts."""
        with self._lock:
            s = self._roll_day()
            if s.password_fails.get(ids.visitor[:16], 0) >= PASSWORD_FAILS_PER_DAY:
                return None
            ok = bool(expected) and hmac.compare_digest(typed.encode("utf-8"), expected.encode("utf-8"))
            if not ok:
                s.password_fails[ids.visitor[:16]] = s.password_fails.get(ids.visitor[:16], 0) + 1
            return ok

    def snapshot(self) -> dict:
        with self._lock:
            s = self._roll_day()
            return {"day": s.day, "visitor_spend_krw": s.visitor_spend_krw, "presenter_spend_krw": s.presenter_spend_krw,
                    "reserved_krw": s.reserved_krw, "month_visitor_krw": self._month_visitor_krw,
                    "runs": sum(s.visitor_counts.values())}

    def remaining(self, ids: VisitorIds) -> dict:
        with self._lock:
            s = self._roll_day()
            return {task: max(0, cap - s.visitor_counts.get((ids.visitor[:16], task), 0)) for task, cap in VISITOR_CAPS.items()}


def _rows(day_dir: Path):
    for path in day_dir.glob("*.json"):
        try:
            yield json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # a half-uploaded or foreign file never blocks startup


def _apply(state: DayState, row: dict) -> None:
    if row.get("presenter"):
        state.presenter_spend_krw += int(row.get("cost_krw", 0))
        return
    state.visitor_spend_krw += int(row.get("cost_krw", 0))
    if not row.get("refunded"):
        key = (row.get("visitor", ""), row.get("task", ""))
        state.visitor_counts[key] = state.visitor_counts.get(key, 0) + 1
        state.ip_runs[row.get("ip", "")] = state.ip_runs.get(row.get("ip", ""), 0) + 1


def write_once(path: Path, row: dict) -> None:
    """Create, write, close. Mode "x" refuses to overwrite; no rename, no append."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))


def load_or_create_secret(path: Path) -> bytes:
    """Random 32-byte HMAC key kept in the private bucket (or pass a Space secret instead)."""
    env = os.environ.get("VISITOR_SALT", "")
    if env:
        return env.encode("utf-8")
    if path.is_file():
        return bytes.fromhex(path.read_text(encoding="ascii").strip())
    key = secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="ascii") as handle:
        handle.write(key.hex())
    return key
