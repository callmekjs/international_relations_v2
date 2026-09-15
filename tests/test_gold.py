import json
from collections import Counter
from pathlib import Path

import pytest

from assistant.citations import cite_key
from evals.gold import KIND_COUNTS, load_gold, problems

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "corpus" / "pages.jsonl"
needs_corpus = pytest.mark.skipif(not PAGES.is_file(), reason="corpus/가 없음: python -m prep.build 로 먼저 만든다")


def test_gold_file_is_well_formed():
    items = load_gold()
    assert [item["id"] for item in items] == [f"g{n:02d}" for n in range(1, 19)]
    assert Counter(item["kind"] for item in items) == Counter(KIND_COUNTS)
    assert {item["id"]: problems(item) for item in items if problems(item)} == {}


@pytest.fixture(scope="module")
def page_keys():
    rows = [json.loads(line) for line in PAGES.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["page_id"]: (row["citable"], cite_key(row["text"])) for row in rows}


@needs_corpus
def test_every_fact_is_on_its_gold_pages(page_keys):
    bad: dict[str, list[str]] = {}
    for item in load_gold():
        for page_id in item["gold_pages"]:
            if page_id not in page_keys or not page_keys[page_id][0]:
                bad.setdefault(item["id"], []).append(f"인용할 수 없는 쪽 {page_id}")
        text = "|".join(page_keys[p][1] for p in item["gold_pages"] if p in page_keys)
        for group in item["facts"]:
            if not any(cite_key(alternative) in text for alternative in group):
                bad.setdefault(item["id"], []).append(f"정답 쪽에 없는 사실 {group}")
    assert bad == {}


@needs_corpus
def test_not_found_terms_appear_nowhere(page_keys):
    found = {}
    for item in load_gold():
        for term in item["absent_terms"]:
            hits = [page_id for page_id, (_, key) in page_keys.items() if cite_key(term) in key]
            if hits:
                found[item["id"]] = (term, hits[:3])
    assert found == {}
