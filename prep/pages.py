"""Per-half page records for corpus/pages.jsonl."""
from __future__ import annotations

import pymupdf

from prep import toc as toc_mod
from prep.volumes import VOLUMES


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
