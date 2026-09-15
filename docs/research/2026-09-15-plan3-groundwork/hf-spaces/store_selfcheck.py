"""Prototype: storage self-check to run once at Space startup (Plan 3 groundwork, topic hf-spaces).

The bucket volume is an hf-mount FUSE mount. Its exact write mode inside Spaces is not documented, so the app
should find out on the real mount and log ONE JSON line (visible in the Space "Logs" tab / `hf spaces logs`).
Nothing personal is written: probe files hold a timestamp only and are removed afterwards when possible.

    python store_selfcheck.py /data          # on the Space (STORE_DIR)
    python store_selfcheck.py ./tmp-store    # locally, to test the code
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path


def _probe(results: dict, name: str, fn) -> None:
    started = time.perf_counter()
    try:
        detail = fn()
        results[name] = {"ok": True, "ms": round((time.perf_counter() - started) * 1000, 1), **(detail or {})}
    except Exception as exc:  # the check must never crash the app
        results[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}


def run_selfcheck(store_dir: str | os.PathLike) -> dict:
    root = Path(store_dir)
    probe_dir = root / "_selfcheck" / uuid.uuid4().hex[:12]
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results: dict = {"store_dir": str(root), "exists": root.is_dir(), "uid": getattr(os, "getuid", lambda: None)(),
                     "system": os.environ.get("SYSTEM"), "space_id": os.environ.get("SPACE_ID")}
    if sys.platform.startswith("linux"):
        try:
            mounts = subprocess.run(["mount"], capture_output=True, text=True, timeout=5).stdout
            results["mount_line"] = next((line for line in mounts.splitlines() if f" {root} " in line), None)
        except Exception as exc:
            results["mount_line"] = f"unavailable: {type(exc).__name__}"

    def mkdir():
        probe_dir.mkdir(parents=True, exist_ok=True)

    def write_new_file():  # the pattern the app relies on: create, write sequentially, close
        (probe_dir / "new.json").write_text(json.dumps({"at": stamp}), encoding="utf-8")
        return {"read_back": json.loads((probe_dir / "new.json").read_text(encoding="utf-8"))["at"] == stamp}

    def overwrite_in_place():
        (probe_dir / "new.json").write_text(json.dumps({"at": stamp, "v": 2}), encoding="utf-8")
        return {"read_back": json.loads((probe_dir / "new.json").read_text(encoding="utf-8")).get("v") == 2}

    def replace_via_rename():
        tmp = probe_dir / "swap.json.tmp"
        tmp.write_text("{}", encoding="utf-8")
        os.replace(tmp, probe_dir / "new.json")
        return {"read_back": (probe_dir / "new.json").read_text(encoding="utf-8") == "{}"}

    def append():
        with open(probe_dir / "log.jsonl", "a", encoding="utf-8") as f:
            f.write("{}\n")
        with open(probe_dir / "log.jsonl", "a", encoding="utf-8") as f:
            f.write("{}\n")
        return {"lines": len((probe_dir / "log.jsonl").read_text(encoding="utf-8").splitlines())}

    def fsync_file():
        with open(probe_dir / "sync.bin", "wb") as f:
            f.write(b"x" * 4096)
            f.flush()
            os.fsync(f.fileno())

    def sqlite_delete_journal():  # same pragmas trackio uses on Spaces bucket mounts
        con = sqlite3.connect(probe_dir / "probe.db", timeout=5)
        try:
            con.execute("PRAGMA journal_mode = DELETE")
            con.execute("PRAGMA locking_mode = EXCLUSIVE")
            con.execute("CREATE TABLE t (k TEXT PRIMARY KEY, n INTEGER)")
            con.execute("INSERT INTO t VALUES ('a', 1)")
            con.execute("UPDATE t SET n = n + 1 WHERE k = 'a'")
            con.commit()
            return {"n": con.execute("SELECT n FROM t").fetchone()[0]}
        finally:
            con.close()

    def flock():
        import fcntl  # Linux only
        with open(probe_dir / "lock", "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def listdir():
        return {"entries": len(list(probe_dir.iterdir()))}

    def cleanup():
        for p in sorted(probe_dir.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        probe_dir.rmdir()

    for name, fn in [("mkdir", mkdir), ("write_new_file", write_new_file), ("overwrite_in_place", overwrite_in_place),
                     ("replace_via_rename", replace_via_rename), ("append", append), ("fsync", fsync_file),
                     ("sqlite_delete_journal", sqlite_delete_journal), ("flock", flock), ("listdir", listdir),
                     ("cleanup", cleanup)]:
        _probe(results, name, fn)
    results["safe_for_write_once_files"] = all(results[k]["ok"] for k in ("mkdir", "write_new_file", "listdir"))
    return results


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STORE_DIR", "/data")
    print("STORE_SELFCHECK " + json.dumps(run_selfcheck(target), ensure_ascii=False), flush=True)
