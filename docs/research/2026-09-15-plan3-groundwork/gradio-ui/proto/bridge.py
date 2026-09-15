"""Bridge a synchronous assistant.run(task, inputs, on_event) into a generator a Gradio event can iterate.

The run happens in a worker thread; on_event puts (kind, data, emit time) on a queue; the generator yields
each item as soon as it arrives, plus a "tick" every heartbeat_s so Gradio gets a chance to close the
generator (Stop button, tab closed). Cancelling works by raising RunCancelled from on_event at the
run's next progress event; the worker still finishes with a Result (so the cost of turns already paid
for is kept) and hands it to on_result even when nobody is watching any more.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Iterator

TERMINAL_KINDS = ("notice", "done")  # emitted by runner.finish(); never interrupt those


class RunCancelled(Exception):
    """Raised inside on_event to stop the run at its next progress event."""


class RunHandle:
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.cancel = threading.Event()
        self.cancel_reason: str | None = None
        self.finished = threading.Event()

    def stop(self, reason: str) -> None:
        if not self.cancel.is_set():
            self.cancel_reason = reason
            self.cancel.set()


class EventLog:
    """Server-side timing log (JSONL) so a headless client can compare arrival times with emit times."""

    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()

    def write(self, **row) -> None:
        if self.path is None:
            return
        row = {"t": time.time(), **row}
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def stream_run(start: Callable[[Callable[..., None]], object], handle: RunHandle, *,
               on_result: Callable[[object, RunHandle], None] | None = None,
               deadline_s: float = 240.0, heartbeat_s: float = 1.0,
               log: EventLog | None = None) -> Iterator[tuple]:
    """Yields ("event", kind, data, t_emit) ..., then ("result", result) or ("crash", exc).
    Also yields ("tick", elapsed_s) every heartbeat_s while the run is quiet."""
    log = log or EventLog(None)
    items: "queue.Queue[tuple]" = queue.Queue()

    def on_event(kind: str, **data) -> None:
        if handle.cancel.is_set() and kind not in TERMINAL_KINDS:
            log.write(run=handle.id, where="worker", what="cancel_raised", kind=kind, reason=handle.cancel_reason)
            raise RunCancelled(handle.cancel_reason or "cancelled")
        t = time.time()
        log.write(run=handle.id, where="worker", what="emit", kind=kind, data=data)
        items.put(("event", kind, data, t))

    def work() -> None:
        try:
            result = start(on_event)
            log.write(run=handle.id, where="worker", what="run_returned", status=getattr(result, "status", None),
                      notice=getattr(result, "notice", None), reason=handle.cancel_reason)
            if on_result is not None:
                on_result(result, handle)  # cost accounting and record saving happen here, watched or not
            items.put(("result", result))
        except BaseException as exc:  # noqa: BLE001 - the UI must always get an end
            log.write(run=handle.id, where="worker", what="crash", error=repr(exc))
            items.put(("crash", exc))
        finally:
            handle.finished.set()

    threading.Thread(target=work, name=f"assistant-run-{handle.id}", daemon=True).start()
    started = time.monotonic()
    try:
        while True:
            try:
                item = items.get(timeout=heartbeat_s)
            except queue.Empty:
                elapsed = time.monotonic() - started
                if elapsed > deadline_s:
                    handle.stop("deadline")
                yield ("tick", round(elapsed, 1))
                continue
            yield item
            if item[0] in ("result", "crash"):
                return
    except GeneratorExit:
        # Gradio closes the generator on Stop (/cancel) and when the client went away.
        if os.environ.get("BRIDGE_CANCEL_ON_CLOSE", "1") == "1":  # "0" = control run: naive bridge
            handle.stop("generator_closed")
        log.write(run=handle.id, where="generator", what="closed")
        raise
