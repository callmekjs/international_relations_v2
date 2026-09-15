"""Page-level BM25 over character bigrams (bm25s), chosen in the 2026-09-14 groundwork (D7)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import bm25s
import numpy as np

from assistant.textnorm import bigram_tokens, normalize

K1 = 1.5
B = 0.75
SNIPPET_WIDTH = 150
_WORDS = re.compile(r"[\w·]+")


@dataclass
class SearchIndex:
    page_ids: list[str]
    years: np.ndarray
    texts: list[str]  # normalized one-line page text, for snippets
    engine: bm25s.BM25


def build_index(pages: list[dict]) -> SearchIndex:
    """pages: rows with page_id, year and text. Pass only citable pages."""
    if not pages:
        raise ValueError("no pages to index")
    engine = bm25s.BM25(k1=K1, b=B, method="lucene")
    engine.index([bigram_tokens(p["text"]) for p in pages], show_progress=False)
    return SearchIndex(
        page_ids=[p["page_id"] for p in pages],
        years=np.array([int(p["year"]) for p in pages], dtype=np.int32),
        texts=[normalize(p["text"]) for p in pages],
        engine=engine,
    )


def search(index: SearchIndex, query: str, years: list[int] | None = None, k: int = 10,
           balance_years: bool = False) -> list[dict]:
    """Top-k pages. years filters by covered year. balance_years interleaves the per-year
    rankings so every requested year is represented (groundwork D9)."""
    tokens = bigram_tokens(query)
    if not tokens or k <= 0:
        return []
    scores = np.asarray(index.engine.get_scores(tokens), dtype=np.float32)
    wanted = sorted(set(years)) if years else []
    if balance_years and len(wanted) > 1:
        per_year = [_top(scores, index.years == year, k) for year in wanted]
        hits: list[tuple[int, float]] = []
        rank = 0
        while len(hits) < k and any(rank < len(ranked) for ranked in per_year):
            for ranked in per_year:
                if rank < len(ranked) and len(hits) < k:
                    hits.append(ranked[rank])
            rank += 1
    else:
        hits = _top(scores, np.isin(index.years, wanted) if wanted else None, k)
    return [{"page_id": index.page_ids[i], "year": int(index.years[i]), "rank": n, "score": round(score, 4),
             "snippet": _snippet(index.texts[i], query)}
            for n, (i, score) in enumerate(hits, 1)]


def _top(scores: np.ndarray, mask: np.ndarray | None, k: int) -> list[tuple[int, float]]:
    s = scores.copy()
    if mask is not None:
        s[~mask] = -np.inf
    order = np.argsort(-s, kind="stable")[:k]
    return [(int(i), float(s[i])) for i in order if s[i] > 0]


def _snippet(text: str, query: str, width: int = SNIPPET_WIDTH) -> str:
    """About `width` characters around the first query word found (page start if none)."""
    words = sorted({w for w in _WORDS.findall(normalize(query)) if len(w) >= 2}, key=len, reverse=True)
    pos = -1
    for word in words:
        candidates = (word, word[:-1]) if len(word) >= 3 else (word,)
        for candidate in candidates:
            pos = text.find(candidate)
            if pos >= 0:
                break
        if pos >= 0:
            break
    start = max(0, pos - width // 3) if pos >= 0 else 0
    return text[start:start + width]


def save_index(index: SearchIndex, directory: Path) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    index.engine.save(str(directory / "bm25s"), show_progress=False)
    meta = {"tokenizer": "bigram", "k1": K1, "b": B, "page_ids": index.page_ids,
            "years": index.years.tolist(), "texts": index.texts}
    (directory / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def load_index(directory: Path) -> SearchIndex:
    directory = Path(directory)
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    engine = bm25s.BM25.load(str(directory / "bm25s"), show_progress=False)
    return SearchIndex(meta["page_ids"], np.array(meta["years"], dtype=np.int32), meta["texts"], engine)
