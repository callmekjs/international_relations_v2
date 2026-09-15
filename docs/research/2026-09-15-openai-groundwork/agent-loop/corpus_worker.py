"""Read-only corpus tool worker. Runs under the PROJECT venv (bm25s etc.).

Protocol: one JSON request per stdin line -> one '@@JSON@@{...}' line on stdout.
Requests: {"op": "search", "query": str, "years": [int] | null, "k": int}
          {"op": "read_pages", "page_ids": [str]}
          {"op": "get_toc", "year": int}
Never writes into the project (bytecode writing disabled).
"""
import json
import sys

sys.dont_write_bytecode = True
ROOT = sys.argv[1]
sys.path.insert(0, ROOT)

from pathlib import Path  # noqa: E402

from assistant.corpus import Corpus  # noqa: E402


def _jsonable(o):
    return o.item() if hasattr(o, "item") else str(o)


def main() -> None:
    corpus = Corpus(Path(ROOT) / "corpus")
    sys.stdout.write("@@READY@@\n")
    sys.stdout.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            op = req["op"]
            if op == "search":
                res = corpus.search(req["query"], req.get("years"), int(req.get("k") or 10))
            elif op == "read_pages":
                res = corpus.read_pages(list(req["page_ids"]))
            elif op == "get_toc":
                res = corpus.get_toc(int(req["year"]))
            else:
                raise ValueError(f"unknown op {op!r}")
            out = {"ok": True, "result": res}
        except Exception as exc:  # report, keep serving
            out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write("@@JSON@@" + json.dumps(out, ensure_ascii=False, default=_jsonable) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
