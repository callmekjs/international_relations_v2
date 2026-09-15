"""No-LLM check that the existing citation checker (assistant.citations.verify_answer, read-only import) grades a
sections -> sentences -> citations summary, and how long it takes on the largest chapter.

Synthetic answers are built from real corpus paragraphs. The saved output keeps only lengths and grades,
never the white-paper text.

    PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe verify_summary_check.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, "C:/international_relations")
from assistant.citations import ShownPage, verify_answer  # noqa: E402

from summary_proto import build_chapter, build_request, verify_summary  # noqa: E402

CORPUS = Path("C:/international_relations/corpus")
OUT = Path(__file__).with_name("verify_summary_check_output.json")


def shown_pages(raw: dict) -> dict:
    return {pid: ShownPage(*values) for pid, values in raw.items()}


def synthetic_answer(payload: dict, shown: dict, mode: str) -> dict:
    """mode 'mixed': one citation of each kind per section; mode 'all_miss': every quote absent (worst-case scan)."""
    sections = []
    for s_index, section in enumerate(payload["sections"]):
        sentences = []
        pages = section["pages"]
        for i in range(section["target_sentences"]):
            page = pages[(i * 3) % len(pages)]
            pid = page["page_id"]
            numbers = [n for n, t in page["paragraphs"].items() if len(t) >= 60] or list(page["paragraphs"])
            n = int(numbers[i % len(numbers)])
            text = page["paragraphs"][str(n)]
            quote = text[10:45]
            kind = "all_miss" if mode == "all_miss" else ["exact", "wrong_paragraph", "wrong_page", "paraphrase",
                                                          "unread_page", "short"][(i + s_index) % 6]
            if kind == "exact":
                cite = {"page_id": pid, "paragraph": n, "quote": quote}
            elif kind == "wrong_paragraph":
                other = 1 if n != 1 else 2
                cite = {"page_id": pid, "paragraph": other if str(other) in page["paragraphs"] else n, "quote": quote}
            elif kind == "wrong_page":
                neighbour = pages[(i * 3 + 1) % len(pages)]["page_id"] if len(pages) > 1 else pid
                cite = {"page_id": neighbour, "paragraph": 1, "quote": quote}
            elif kind in ("paraphrase", "all_miss"):
                cite = {"page_id": pid, "paragraph": n, "quote": quote[::-1] + "없는말없는말없는말"}
            elif kind == "unread_page":
                cite = {"page_id": "2019-p001L", "paragraph": 1, "quote": quote}
            else:
                cite = {"page_id": pid, "paragraph": n, "quote": quote[:8]}
            sentences.append({"text": f"문장 {s_index + 1}-{i + 1}", "citations": [cite], "_kind": kind})
        sections.append({"title": section["title"], "sentences": sentences})
    overview = [{"text": "개요", "citations": sections[0]["sentences"][0]["citations"], "_kind": "exact_overview"}]
    return {"sections": sections, "overview": overview}


def main() -> None:
    rows = [json.loads(line) for line in open(CORPUS / "pages.jsonl", encoding="utf-8")]
    results = {}
    for year, label in ((2025, "제7장"), (2023, "제3장")):
        text, raw_shown, meta = build_chapter(rows, year, label, style="B")
        payload = json.loads(text)
        shown = shown_pages(raw_shown)
        entry = {"pages": meta["pages"], "sections": len(meta["sections"]), "target_sentences": meta["target_sentences"],
                 "payload_utf8_bytes": len(text.encode("utf-8")),
                 "request_body_utf8_bytes": len(json.dumps(build_request(model="gpt-5.6-sol", payload_text=text,
                                                                         max_output_tokens=32000,
                                                                         safety_identifier="0" * 64, flex=True),
                                                           ensure_ascii=False).encode("utf-8"))}
        for mode in ("mixed", "all_miss"):
            answer = synthetic_answer(payload, shown, mode)
            kinds = [s["_kind"] for sec in answer["sections"] for s in sec["sentences"]] + ["exact_overview"]
            started = time.perf_counter()
            checked = verify_summary(answer, shown, verify_answer)
            elapsed = time.perf_counter() - started
            flat = [s for sec in checked["sections"] for s in sec["sentences"]] + checked["overview"]
            by_kind = Counter()
            for kind, sentence in zip(kinds, flat):
                c = sentence["citations"][0]
                by_kind[f"{kind} -> {c['grade']}/{c['reason']}/{c['corrected']}"] += 1
            entry[mode] = {"verify_seconds": round(elapsed, 3), "sentence_counts": checked["counts"],
                           "references": len(checked["references"]), "by_kind": dict(by_kind),
                           "sections_regrouped": [len(sec["sentences"]) for sec in checked["sections"]],
                           "overview_sentences": len(checked["overview"])}
        results[f"{year} {label}"] = entry
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
