"""Build corpus/ from the six PDFs.

    PYTHONUTF8=1 .venv/Scripts/python -m prep.build [--out corpus] [--years 2020 2021 ...]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from assistant.search_index import build_index, save_index
from prep.pages import build_records
from prep.toc_build import build_toc
from prep.volumes import CORPUS_YEARS, MISSING, ROOT, VOLUMES


def build(out_dir: Path, years: list[int]) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tocs: dict[str, list[dict]] = {}
    pages: list[dict] = []
    for year in years:
        tocs[str(year)] = build_toc(year)
        pages.extend(build_records(year, tocs[str(year)]))
    _write_json(out_dir / "volumes.json", {
        "corpus_years": list(CORPUS_YEARS),
        "volumes": [{"year": y, "edition_title": VOLUMES[y].edition_title, "file_name": VOLUMES[y].file_name}
                    for y in years],
    })
    _write_json(out_dir / "toc.json", tocs)
    _write_json(out_dir / "missing.json", [item for item in MISSING if item["year"] in years])
    with open(out_dir / "pages.jsonl", "w", encoding="utf-8") as f:
        for row in pages:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    citable = [p for p in pages if p["citable"]]
    save_index(build_index(citable), out_dir / "index")
    return {
        "years": list(years),
        "halves": len(pages),
        "citable": len(citable),
        "citable_by_year": {str(y): sum(p["citable"] for p in pages if p["year"] == y) for y in years},
    }


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build corpus/ from the white paper PDFs")
    parser.add_argument("--out", type=Path, default=ROOT / "corpus")
    parser.add_argument("--years", type=int, nargs="+", default=list(CORPUS_YEARS))
    args = parser.parse_args()
    started = time.time()
    stats = build(args.out, args.years)
    stats["seconds"] = round(time.time() - started, 1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
