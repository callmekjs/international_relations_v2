"""Independent recount of chapter sizes (verifier). Read-only on the corpus, no network.
Does not import the researcher's summary_proto; payload B is rebuilt from the report's description."""
from __future__ import annotations

import json
import re
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

import tiktoken

CORPUS = Path("C:/international_relations/corpus")
HERE = Path(__file__).resolve().parent
ENC = tiktoken.get_encoding("o200k_base")
PAT = re.compile(r"^[0-9]{4}-p[0-9]{3}[LR]$")


def ntok(s: str) -> int:
    return len(ENC.encode(s))


def paras(text: str) -> list[str]:
    return [line for line in text.split("\n") if line.strip()]


def target(n: int) -> int:
    return 2 if n <= 3 else 3 if n <= 9 else 4 if n <= 19 else 5


def join(label, title):
    if not label:
        return None
    return f"{label} {title}" if title and title != label else label


rows = [json.loads(l) for l in open(CORPUS / "pages.jsonl", encoding="utf-8")]
toc = {int(y): e for y, e in json.loads((CORPUS / "toc.json").read_text(encoding="utf-8")).items()}
out = {}

# page_id pattern over all pages
bad_ids = [r["page_id"] for r in rows if not PAT.match(r["page_id"])]
out["page_ids_not_matching_pattern"] = len(bad_ids)
out["page_ids_total"] = len(rows)
out["single_page_rows"] = sum(1 for r in rows if r.get("single_page"))

chapters = []
by = defaultdict(list)
for r in rows:
    by[(r["year"], r["chapter_label"])].append(r)
for (year, label), members in sorted(by.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
    if not label or label == "부록":
        continue
    cit = [r for r in members if r["citable"]]
    entry = next(e for e in toc[year] if e["level"] == 1 and e["label"] == label)
    printed = {r["printed_page"] for r in members if r["printed_page"] is not None}
    gaps = [n for n in range(entry["printed_page"], entry["printed_end"] + 1) if n not in printed]
    noncit = Counter(r["kind"] for r in members if not r["citable"])
    noncit_text_chars = sum(len(r["text"]) for r in members if not r["citable"])
    no_section = sum(1 for r in cit if not r["section_label"])
    groups = OrderedDict()
    for p in cit:
        groups.setdefault(join(p["section_label"], p["section_title"]) or "(절 없음)", []).append(p)
    # contiguity of sections: a section title that reappears after another section
    seq = [join(p["section_label"], p["section_title"]) for p in cit]
    runs = [s for i, s in enumerate(seq) if i == 0 or seq[i - 1] != s]
    noncontig = [s for s, c in Counter(runs).items() if c > 1]
    toc_sections = [e for e in toc[year] if e["level"] == 2 and e.get("chapter_no") == entry["no"]]
    payload = {"year": year, "edition": cit[0]["edition_title"], "chapter": join(label, cit[0]["chapter_title"]),
               "sections": [{"title": t, "target_sentences": target(len(g)),
                             "pages": [{"page_id": p["page_id"],
                                        "paragraphs": {str(n): x for n, x in enumerate(paras(p["text"]), 1)}}
                                       for p in g]} for t, g in groups.items()]}
    text_b = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    chars = sum(len(r["text"]) for r in cit)
    longest_para = max((len(x) for r in cit for x in paras(r["text"])), default=0)
    npar = sum(len(paras(r["text"])) for r in cit)
    maxpar_page = max((len(paras(r["text"])) for r in cit), default=0)
    chapters.append({
        "year": year, "label": label, "printed": [entry["printed_page"], entry["printed_end"]],
        "pages_all": len(members), "citable": len(cit), "noncitable_kinds": dict(noncit),
        "noncitable_text_chars": noncit_text_chars, "gaps": gaps, "no_section_label": no_section,
        "sections_pages": len(groups), "sections_toc": len(toc_sections), "noncontiguous_sections": noncontig,
        "chars": chars, "x064": round(chars * 0.64), "text_tokens": ntok("\n".join(r["text"] for r in cit)),
        "payload_B_chars": len(text_b), "payload_B_tokens": ntok(text_b), "targets": sum(target(len(g)) for g in groups.values()),
        "paragraphs": npar, "max_paragraphs_on_a_page": maxpar_page, "longest_paragraph_chars": longest_para,
    })

out["main_chapters"] = len(chapters)
tot = lambda rows_, k: sum(r[k] for r in rows_)  # noqa: E731
c25 = [c for c in chapters if c["year"] == 2025]
out["totals_2025"] = {k: tot(c25, k) for k in ("citable", "chars", "x064", "text_tokens", "payload_B_tokens", "targets")}
out["totals_all"] = {k: tot(chapters, k) for k in ("citable", "chars", "x064", "text_tokens", "payload_B_tokens", "targets")}
big = max(chapters, key=lambda c: c["payload_B_tokens"])
small = min(chapters, key=lambda c: c["payload_B_tokens"])
srt = sorted(chapters, key=lambda c: c["payload_B_tokens"])
out["largest"] = big
out["smallest"] = small
out["median_index_22"] = srt[len(srt) // 2]
out["median_index_21"] = srt[len(srt) // 2 - 1]
out["chapters_with_gaps"] = [(c["year"], c["label"], c["gaps"]) for c in chapters if c["gaps"]]
out["chapters_with_noncitable_pages"] = [(c["year"], c["label"], c["noncitable_kinds"], c["noncitable_text_chars"])
                                         for c in chapters if c["noncitable_kinds"]]
out["chapters_section_count_mismatch_vs_toc"] = [(c["year"], c["label"], c["sections_pages"], c["sections_toc"])
                                                 for c in chapters if c["sections_pages"] != c["sections_toc"]]
out["chapters_noncontiguous_sections"] = [(c["year"], c["label"], c["noncontiguous_sections"]) for c in chapters
                                          if c["noncontiguous_sections"]]
out["citable_pages_without_section"] = sum(c["no_section_label"] for c in chapters)
out["payload_tokens_per_payload_char_range"] = [round(min(c["payload_B_tokens"] / c["payload_B_chars"] for c in chapters), 3),
                                                round(max(c["payload_B_tokens"] / c["payload_B_chars"] for c in chapters), 3)]
out["max_paragraphs_on_a_page"] = max(c["max_paragraphs_on_a_page"] for c in chapters)
out["per_chapter"] = [{k: c[k] for k in ("year", "label", "citable", "chars", "x064", "text_tokens", "payload_B_tokens",
                                         "payload_B_chars", "sections_pages", "targets")} for c in chapters]
(HERE / "recount_output.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "per_chapter"}, ensure_ascii=False, indent=1))
