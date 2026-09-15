"""Read-only access to corpus/ for the assistant tools (no PyMuPDF, no LLM)."""
from __future__ import annotations

import json
from pathlib import Path

from assistant.search_index import load_index
from assistant.search_index import search as search_index

MAX_READ_PAGES = 5


class Corpus:
    def __init__(self, directory: Path):
        directory = Path(directory)
        volumes = _read_json(directory / "volumes.json")
        self.corpus_years: list[int] = volumes["corpus_years"]
        self.volumes: dict[int, dict] = {v["year"]: v for v in volumes["volumes"]}
        self.toc: dict[int, list[dict]] = {int(y): entries for y, entries in _read_json(directory / "toc.json").items()}
        self.missing: list[dict] = _read_json(directory / "missing.json")
        with open(directory / "pages.jsonl", encoding="utf-8") as f:
            self.pages: dict[str, dict] = {row["page_id"]: row for row in map(json.loads, f)}
        self.index = load_index(directory / "index")

    def label(self, page: dict) -> str:
        number = f"{page['printed_page']}쪽" + ("" if page["label_printed"] else "(번호 미인쇄)")
        return f"{page['year']}년치 · 「{page['edition_title']}」 {number}"

    def search(self, query: str, years: list[int] | None = None, k: int = 10) -> dict:
        wanted = sorted(set(years or []))
        outside = [y for y in wanted if y not in self.corpus_years]
        inside = [y for y in wanted if y in self.corpus_years]
        if wanted and not inside:
            return {"hits": [], "out_of_range_years": outside, "corpus_years": self.corpus_years}
        hits = search_index(self.index, query, inside or None, k, balance_years=len(inside) > 1)
        return {"hits": [self._hit(h) for h in hits], "out_of_range_years": outside,
                "corpus_years": self.corpus_years}

    def read_pages(self, page_ids: list[str]) -> dict:
        if len(page_ids) > MAX_READ_PAGES:
            raise ValueError(f"한 번에 최대 {MAX_READ_PAGES}쪽까지 읽을 수 있습니다")
        pages, not_found, not_citable = [], [], []
        for pid in page_ids:
            page = self.pages.get(pid)
            if page is None:
                not_found.append(pid)
            elif not page["citable"]:
                not_citable.append(pid)
            else:
                pages.append({**self._where(page),
                              "paragraphs": [line for line in page["text"].split("\n") if line.strip()]})
        return {"pages": pages, "not_found": not_found, "not_citable": not_citable}

    def get_toc(self, year: int) -> dict:
        if year not in self.toc:
            return {"not_in_corpus": True, "year": year, "corpus_years": self.corpus_years}
        entries = [{"level": e["level"], "label": e["label"], "title": e["title"],
                    "printed_page": e.get("printed_page"), "printed_end": e.get("printed_end")}
                   for e in self.toc[year]]
        return {"year": year, "edition_title": self.volumes[year]["edition_title"], "entries": entries,
                "missing": [m for m in self.missing if m["year"] == year]}

    def _hit(self, hit: dict) -> dict:
        return {**self._where(self.pages[hit["page_id"]]), "snippet": hit["snippet"], "score": hit["score"]}

    def _where(self, page: dict) -> dict:
        return {
            "page_id": page["page_id"],
            "label": self.label(page),
            "year": page["year"],
            "chapter": _join(page["chapter_label"], page["chapter_title"]),
            "section": _join(page["section_label"], page["section_title"]),
            "is_appendix": page["is_appendix"],
        }


def _join(label: str | None, title: str | None) -> str | None:
    if not label:
        return None
    return f"{label} {title}" if title and title != label else label


def _read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
