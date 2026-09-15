"""Per-chapter sizes for the summary feature, measured from the local corpus (read-only). No network.

    PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe chapter_sizes.py

Writes chapters.json and chapters.md next to this file.
"""
from __future__ import annotations

import json
import random
import statistics
from collections import Counter
from pathlib import Path

import tiktoken

from summary_proto import (SUMMARY_ANSWER_FORMAT, SUMMARY_INSTRUCTIONS, build_chapter, paragraphs_of)

CORPUS = Path("C:/international_relations/corpus")
HERE = Path(__file__).resolve().parent
ENC = tiktoken.get_encoding("o200k_base")
TOKENS_PER_CHAR = 0.64          # measured ratio (groundwork token-costs 2.1)
REQUEST_OVERHEAD = 10           # groundwork: [developer, user] chapter request = tiktoken(body) + tiktoken(prompt) + 10


def ntok(text: str) -> int:
    return len(ENC.encode(text))


def main() -> None:
    rows = [json.loads(line) for line in open(CORPUS / "pages.jsonl", encoding="utf-8")]
    toc = {int(y): entries for y, entries in json.loads((CORPUS / "toc.json").read_text(encoding="utf-8")).items()}
    missing = json.loads((CORPUS / "missing.json").read_text(encoding="utf-8"))

    instructions_tokens = ntok(SUMMARY_INSTRUCTIONS)
    schema_json_tokens = ntok(json.dumps(SUMMARY_ANSWER_FORMAT["schema"], ensure_ascii=False, separators=(",", ":")))

    # --- tokens per output sentence (visible JSON), from real paragraphs -------------------------------------
    rng = random.Random(20260919)
    body = [r for r in rows if r["citable"] and r["chapter_label"] and not r["is_appendix"]]
    samples_default, samples_compact = [], []
    for page in rng.sample(body, 200):
        paras = [p for p in paragraphs_of(page["text"]) if len(p) >= 80] or paragraphs_of(page["text"])
        para = rng.choice(paras)
        n = paragraphs_of(page["text"]).index(para) + 1
        cites = [{"page_id": page["page_id"], "paragraph": n, "quote": para[5:40]} for _ in range(rng.choice([1, 2]))]
        sentence = {"text": para[:70], "citations": cites}
        samples_default.append(ntok(json.dumps(sentence, ensure_ascii=False)))
        samples_compact.append(ntok(json.dumps(sentence, ensure_ascii=False, separators=(",", ":"))))
    tokens_per_sentence = round(statistics.mean(samples_default), 1)

    out = []
    groups = sorted({(r["year"], r["chapter_label"]) for r in rows}, key=lambda k: (k[0], k[1] is not None,
                                                                                     k[1] == "부록", k[1] or ""))
    for year, label in groups:
        members = [r for r in rows if r["year"] == year and r["chapter_label"] == label]
        citable = [r for r in members if r["citable"]]
        entry = next((e for e in toc.get(year, []) if e["level"] == 1 and e["label"] == label), None)
        kind = "front_matter" if label is None else "appendix" if label == "부록" else "chapter"
        text_b, shown, meta = build_chapter(rows, year, label, style="B")
        chars = sum(len(r["text"]) for r in citable)
        chars_no_ws = sum(sum(not c.isspace() for c in r["text"]) for r in citable)
        paragraphs = sum(len(paragraphs_of(r["text"])) for r in citable)
        printed_present = {r["printed_page"] for r in members if r["printed_page"] is not None}
        gaps = []
        if entry and entry.get("printed_page") is not None and entry.get("printed_end") is not None:
            gaps = [n for n in range(entry["printed_page"], entry["printed_end"] + 1) if n not in printed_present]
        if entry and entry.get("printed_page") is not None:
            lo, hi = entry["printed_page"], entry["printed_end"]
        else:  # pages outside every chapter: front matter and the back cover
            lo, hi = min(printed_present, default=0), max(printed_present, default=-1)
        miss = [m for m in missing if m["year"] == year and m["printed_from"] <= hi and m["printed_to"] >= lo
                and (entry is not None or not any(e["level"] == 1 and e["printed_page"] <= m["printed_from"] <= e["printed_end"]
                                                  for e in toc.get(year, [])))]
        row = {
            "year": year, "label": label or "(장 밖)", "title": entry["title"] if entry else None, "kind": kind,
            "printed_range": [entry.get("printed_page"), entry.get("printed_end")] if entry else None,
            "pages_all": len(members), "pages_citable": len(citable),
            "non_citable_by_kind": dict(Counter(f"{r['kind']}" for r in members if not r["citable"])),
            "unnumbered_citable": sum(1 for r in citable if not r["label_printed"]),
            "printed_gaps": gaps, "missing_json": [m["what"] for m in miss],
            "sections": len(meta.get("sections", [])), "target_sentences": meta.get("target_sentences", 0),
            "paragraphs": paragraphs, "chars": chars, "chars_no_ws": chars_no_ws,
            "tokens_est_0.64": round(chars * TOKENS_PER_CHAR),
            "tokens_text_only": ntok("\n".join(r["text"] for r in citable)),
        }
        if citable:
            row["tokens_payload_B"] = ntok(text_b)
            row["tokens_payload_A"] = ntok(build_chapter(rows, year, label, style="A")[0])
            row["tokens_payload_C"] = ntok(build_chapter(rows, year, label, style="C")[0])
            row["input_tokens_est"] = row["tokens_payload_B"] + instructions_tokens + schema_json_tokens + REQUEST_OVERHEAD
            # visible output: sentences + section wrappers + overview (3 sentences) + object braces
            row["visible_output_est"] = round((row["target_sentences"] + 3) * tokens_per_sentence
                                              + row["sections"] * 25 + 20)
            row["corpus_hash"] = meta["corpus_hash"][:12]
        flags = []
        if kind != "chapter":
            flags.append(kind)
        if gaps:
            flags.append(f"printed pages absent from pages.jsonl: {gaps}")
        if miss:
            flags.append("missing.json: " + ", ".join(row["missing_json"]))
        if row["unnumbered_citable"]:
            flags.append(f"{row['unnumbered_citable']} citable pages without a printed number")
        if not citable:
            flags.append("no citable pages")
        row["flags"] = flags
        out.append(row)

    chapters = [r for r in out if r["kind"] == "chapter"]
    by_tokens = sorted(chapters, key=lambda r: r["tokens_payload_B"])
    median = by_tokens[len(by_tokens) // 2]
    totals = {}
    for year in sorted({r["year"] for r in out}):
        ch = [r for r in chapters if r["year"] == year]
        totals[year] = {k: sum(r[k] for r in ch) for k in ("pages_citable", "chars", "tokens_est_0.64",
                                                              "tokens_text_only", "tokens_payload_B", "input_tokens_est",
                                                              "target_sentences", "visible_output_est")}
        totals[year]["chapters"] = len(ch)
    summary = {
        "instructions_tokens": instructions_tokens, "schema_json_tokens": schema_json_tokens,
        "tokens_per_output_sentence_default_json": tokens_per_sentence,
        "tokens_per_output_sentence_compact_json": round(statistics.mean(samples_compact), 1),
        "sentence_sample": {"n": 200, "citations_per_sentence_mean": 1.5, "text_chars": 70, "quote_chars": 35},
        "main_chapters": len(chapters),
        "largest_chapter": {k: by_tokens[-1][k] for k in ("year", "label", "title", "pages_citable",
                                                          "tokens_payload_B", "input_tokens_est", "visible_output_est")},
        "median_chapter": {k: median[k] for k in ("year", "label", "title", "pages_citable", "tokens_payload_B",
                                                  "input_tokens_est", "visible_output_est")},
        "smallest_chapter": {k: by_tokens[0][k] for k in ("year", "label", "title", "pages_citable",
                                                          "tokens_payload_B", "input_tokens_est", "visible_output_est")},
        "totals_main_chapters_by_year": totals,
        "all_main_chapters": {k: sum(r[k] for r in chapters) for k in ("pages_citable", "tokens_payload_B",
                                                                         "input_tokens_est", "visible_output_est")},
        "format_compare_all_main_chapters": {s: sum(r[f"tokens_payload_{s}"] for r in chapters) for s in "ABC"},
    }
    (HERE / "chapters.json").write_text(json.dumps({"summary": summary, "rows": out}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")

    lines = ["| Year | Ch. | Kind | Printed | Citable pp | Sections | Chars | Tokens est (x0.64) | Tokens text (o200k) "
             "| Payload B | Input est | Target sentences | Visible out est | Flags |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in out:
        pr = f"{r['printed_range'][0]}-{r['printed_range'][1]}" if r["printed_range"] else "-"
        lines.append(f"| {r['year']} | {r['label']} | {r['kind']} | {pr} | {r['pages_citable']} | {r['sections']} | "
                     f"{r['chars']:,} | {r['tokens_est_0.64']:,} | {r['tokens_text_only']:,} | "
                     f"{r.get('tokens_payload_B', 0):,} | {r.get('input_tokens_est', 0):,} | {r['target_sentences']} | "
                     f"{r.get('visible_output_est', 0):,} | {'; '.join(r['flags'])} |")
    (HERE / "chapters.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
