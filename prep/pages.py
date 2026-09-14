"""Per-half page records for corpus/pages.jsonl."""
from __future__ import annotations

import pymupdf

from prep import extract
from prep import toc as toc_mod
from prep.volumes import MISSING, VOLUMES

CITABLE_STATUS = {"detected", "inferred"}


def page_id(year: int, pdf_page: int, side: str) -> str:
    return f"{year}-p{pdf_page:03d}{side}"


def list_halves(year: int) -> list[dict]:
    """Every half of the volume in reading order with its printed page label.

    Labels come from prep.toc.page_labels: the folio printed on each half, gaps filled from
    neighbours (groundwork D1). A single-width PDF page is reported as side 'L'."""
    with pymupdf.open(VOLUMES[year].pdf_path) as doc:
        labels, status, _anomalies = toc_mod.page_labels(doc)
    halves = []
    for index, sides in enumerate(labels):
        for key, printed in sides.items():
            halves.append({
                "year": year,
                "pdf_page": index + 1,
                "side": "L" if key == "S" else key,
                "single_page": key == "S",
                "printed_page": printed,
                "label_status": status[index][key],
            })
    return halves


def build_records(year: int, toc: list[dict]) -> list[dict]:
    """One record per half: printed label, chapter/section, kind, citable flag and cleaned text."""
    vol = VOLUMES[year]
    pdf = str(vol.pdf_path)
    missing_pages = {page for item in MISSING if item["year"] == year for page in item["pdf_pages"]}
    dividers = {(d["pdf_page"], "L" if d["side"] == "S" else d["side"])
                for entry in toc if entry["level"] == 1 for d in entry.get("divider") or []}
    records = []
    for half in list_halves(year):
        pdf_page, side = half["pdf_page"], half["side"]
        kind = extract.classify_half(pdf, pdf_page, side)["kind"]
        text = extract.clean_text(extract.extract_half_text(pdf, pdf_page, side), year) if kind == "text" else ""
        where = toc_mod.chapter_of(toc, half["printed_page"])
        chapter = where["chapter"] if where else None
        section = where["section"] if where else None
        citable = (
            kind == "text"
            and bool(text.strip())
            and half["label_status"] in CITABLE_STATUS
            and pdf_page not in missing_pages
            and (pdf_page, side) not in dividers
        )
        records.append({
            "page_id": page_id(year, pdf_page, side),
            "year": year,
            "edition_title": vol.edition_title,
            "pdf_page": pdf_page,
            "side": side,
            "single_page": half["single_page"],
            "printed_page": half["printed_page"],
            "label_printed": half["label_status"] == "detected",
            "label_status": half["label_status"],
            "chapter_label": chapter["label"] if chapter else None,
            "chapter_title": chapter["title"] if chapter else None,
            "section_label": section["label"] if section else None,
            "section_title": section["title"] if section else None,
            "is_appendix": bool(chapter and chapter["label"] == "부록"),
            "kind": kind,
            "citable": citable,
            "text": text,
        })
    return records
