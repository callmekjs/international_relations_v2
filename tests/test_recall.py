import json
from pathlib import Path

import pytest

from assistant.corpus import Corpus
from assistant.textnorm import match_key

pytestmark = [pytest.mark.pdf, pytest.mark.slow]

QUERIES = Path(__file__).with_name("fixtures") / "search_queries.jsonl"


def _is_gold(page: dict, gold: list[dict]) -> bool:
    text = match_key(page["text"])
    return any(page["year"] == g["year"] and any(all(match_key(n) in text for n in needles) for needles in g["any"])
               for g in gold)


def test_keyword_search_recall_at_10(full_corpus_dir):
    corpus = Corpus(full_corpus_dir)
    queries = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    misses = []
    for q in queries:
        hits = corpus.search(q["keywords"], years=q["years"], k=10)["hits"]
        if not any(_is_gold(corpus.pages[h["page_id"]], q["gold"]) for h in hits):
            misses.append(q["id"])
    found = len(queries) - len(misses)
    print(f"recall@10 = {found}/{len(queries)}; misses: {misses}")
    assert len(queries) == 42
    assert found / len(queries) >= 0.90, misses


def test_full_corpus_counts(full_corpus_dir):
    corpus = Corpus(full_corpus_dir)
    halves: dict[int, int] = {}
    for page in corpus.pages.values():
        halves[page["year"]] = halves.get(page["year"], 0) + 1
    assert halves == {2020: 380, 2021: 284, 2022: 346, 2023: 397, 2024: 387, 2025: 342}
    assert len(corpus.missing) == 3
    assert set(corpus.toc) == {2020, 2021, 2022, 2023, 2024, 2025}
