"""Gold questions for the QA eval (spec 8.3) and the shape every item must have."""
from __future__ import annotations

import json
import re
from pathlib import Path

GOLD_PATH = Path(__file__).with_name("gold.jsonl")
FIELDS = ("id", "kind", "question", "years", "expect_status", "facts", "gold_pages", "absent_terms")
FACT_KINDS = ("single_page", "multi_page", "multi_year")
EXPECTED_STATUS = {"single_page": "answered", "multi_page": "answered", "multi_year": "answered",
                   "not_found": "not_found", "not_in_corpus": "not_in_corpus", "refused": "refused"}
KIND_COUNTS = {"single_page": 5, "multi_page": 4, "multi_year": 3, "not_found": 3, "not_in_corpus": 1, "refused": 2}
_PAGE_ID = re.compile(r"^[0-9]{4}-p[0-9]{3}[LR]$")


def load_gold(path: Path = GOLD_PATH) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def problems(item: dict) -> list[str]:
    found: list[str] = []
    if tuple(item) != FIELDS:
        found.append(f"칸 이름과 순서: {list(item)}")
    kind = item.get("kind")
    if kind not in EXPECTED_STATUS:
        return found + [f"kind: {kind}"]
    if item.get("expect_status") != EXPECTED_STATUS[kind]:
        found.append("expect_status")
    question = item.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > 300:
        found.append("question")
    years = item.get("years")
    if years is not None and (not isinstance(years, list) or not all(isinstance(y, int) for y in years)):
        found.append("years")
    facts, pages, absent = item.get("facts"), item.get("gold_pages"), item.get("absent_terms")
    if kind in FACT_KINDS:
        if not facts or not all(isinstance(group, list) and group and all(isinstance(a, str) and a.strip() for a in group)
                                for group in facts):
            found.append("facts")
        if not pages or not all(isinstance(p, str) and _PAGE_ID.match(p) for p in pages):
            found.append("gold_pages")
        if absent != []:
            found.append("absent_terms must be empty")
        if kind == "multi_page" and len(set(pages or [])) < 2:
            found.append("multi_page needs 2+ pages")
        if kind == "multi_year" and len({p[:4] for p in pages or []}) < 2:
            found.append("multi_year needs 2+ years")
    else:
        if facts != [] or pages != []:
            found.append("facts and gold_pages must be empty")
        if kind == "not_found" and not absent:
            found.append("absent_terms")
        if kind != "not_found" and absent != []:
            found.append("absent_terms must be empty")
    return found
