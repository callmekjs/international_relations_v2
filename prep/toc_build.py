"""Chapter/section table of contents per volume (corpus/toc.json)."""
from __future__ import annotations

import json
from pathlib import Path

from prep import toc as toc_mod
from prep.volumes import VOLUMES

MANUAL_TOC_2025 = Path(__file__).with_name("manual_toc_2025.json")


def build_toc(year: int) -> list[dict]:
    """extract_toc from the verified code. The 2025 목차 is an image, so its titles come from body
    headings; replace them with the hand transcription (page numbers stay as detected)."""
    entries = toc_mod.extract_toc(str(VOLUMES[year].pdf_path), year)
    if year == 2025:
        apply_manual_titles(entries, json.loads(MANUAL_TOC_2025.read_text(encoding="utf-8")))
    return entries


def apply_manual_titles(entries: list[dict], manual: dict) -> None:
    chapters = {c["no"]: c["title"] for c in manual["chapters"]}
    sections = {(c["no"], no): title for c in manual["chapters"] for no, title, _page in c["sections"]}
    appendix = {no: title for no, title, _page in manual["appendix"]}
    for entry in entries:
        if entry["level"] == 1:
            entry["title"] = chapters.get(entry.get("no"), entry["title"])
        elif entry.get("chapter_no") is not None:
            entry["title"] = sections.get((entry["chapter_no"], entry["no"]), entry["title"])
        else:
            entry["title"] = appendix.get(entry.get("no"), entry["title"])
