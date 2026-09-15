import json
from collections import Counter
from pathlib import Path

import pytest

from assistant.citations import VERIFIED, check_citation, cite_key
from assistant.corpus import Corpus
from assistant.tools import ToolRunner
from evals.gold import FACT_KINDS, KIND_COUNTS, load_gold, problems

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "corpus" / "pages.jsonl"
needs_corpus = pytest.mark.skipif(not PAGES.is_file(), reason="corpus/가 없음: python -m prep.build 로 먼저 만든다")


def test_gold_file_is_well_formed():
    items = load_gold()
    assert [item["id"] for item in items] == [f"g{n:02d}" for n in range(1, 19)]
    assert Counter(item["kind"] for item in items) == Counter(KIND_COUNTS)
    assert {item["id"]: problems(item) for item in items if problems(item)} == {}


def test_questions_about_a_repeated_event_name_the_one_meant():
    # 2021 had three Korea-Australia summits: Cornwall (6.12), Rome (10.30) and Canberra (12.13).
    # The gold answer is Canberra, so a question about that summit must say December.
    vague = [item["id"] for item in load_gold()
             if "2021년" in item["question"] and "호주 정상회담" in item["question"]
             and "2021년 12월" not in item["question"]]
    assert vague == []


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
def test_every_fact_wording_is_used_somewhere_in_the_corpus(page_keys):
    keys = [key for _, key in page_keys.values()]
    unused: dict[str, list[str]] = {}
    for item in load_gold():
        for group in item["facts"]:
            for alternative in group:
                if not any(cite_key(alternative) in key for key in keys):
                    unused.setdefault(item["id"], []).append(alternative)
    assert unused == {}


@needs_corpus
def test_every_fact_item_has_a_quotable_fact_paragraph_on_a_gold_page():
    # Grading needs a verified citation on a gold page, and a quote needs MIN_QUOTE_CHARS letters and
    # digits. A fact that sits only in a short table cell (2021-p139R, 10 characters) can be cited
    # but never verified, so a correct, honest answer would always fail. Pages are read the way the
    # model reads them, and the whole fact paragraph is graded as the quote.
    corpus = Corpus(PAGES.parent)
    unquotable = []
    for item in load_gold():
        if item["kind"] not in FACT_KINDS:
            continue
        runner = ToolRunner(corpus)
        runner.execute("read_pages", json.dumps({"page_ids": item["gold_pages"]}))
        alternatives = [cite_key(alternative) for group in item["facts"] for alternative in group]
        quotable = [(page.page_id, n) for page in runner.shown.values()
                    for n, paragraph in enumerate(page.paragraphs, 1)
                    if any(alternative in cite_key(paragraph) for alternative in alternatives)
                    and check_citation({"page_id": page.page_id, "paragraph": n, "quote": paragraph},
                                       runner.shown)["grade"] == VERIFIED]
        if not quotable:
            unquotable.append(item["id"])
    assert unquotable == []


@needs_corpus
def test_not_found_terms_appear_nowhere(page_keys):
    found = {}
    for item in load_gold():
        for term in item["absent_terms"]:
            hits = [page_id for page_id, (_, key) in page_keys.items() if cite_key(term) in key]
            if hits:
                found[item["id"]] = (term, hits[:3])
    assert found == {}
