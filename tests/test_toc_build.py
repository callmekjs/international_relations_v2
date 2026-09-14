import json

import pytest

from prep import toc as toc_mod
from prep.toc_build import MANUAL_TOC_2025, build_toc

pytestmark = pytest.mark.pdf

LEVEL2_COUNTS = {2020: 43, 2021: 39, 2022: 40, 2023: 38, 2024: 39, 2025: 38}


@pytest.fixture(scope="module")
def tocs():
    return {year: build_toc(year) for year in LEVEL2_COUNTS}


def test_level2_counts(tocs):
    assert {y: sum(e["level"] == 2 for e in t) for y, t in tocs.items()} == LEVEL2_COUNTS


def test_2021_first_section_uses_printed_folio(tocs):
    first = next(e for e in tocs[2021] if e["level"] == 2)
    assert (first["label"], first["title"], first["printed_page"], first["toc_page"]) == ("제1절", "국제정세 개관", 7, 6)


def test_2021_chapter_starts(tocs):
    chapters = [(e["label"], e["printed_page"]) for e in tocs[2021] if e["level"] == 1]
    assert chapters == [("제1장", 5), ("제2장", 21), ("제3장", 32), ("제4장", 58), ("제5장", 112),
                        ("제6장", 144), ("제7장", 178), ("제8장", 216), ("부록", 226)]


def test_2025_titles_come_from_manual_toc(tocs):
    manual = json.loads(MANUAL_TOC_2025.read_text(encoding="utf-8"))
    want = {(c["no"], no): (title, page) for c in manual["chapters"] for no, title, page in c["sections"]}
    got = {(e["chapter_no"], e["no"]): (e["title"], e["printed_page"])
           for e in tocs[2025] if e["level"] == 2 and e["chapter_no"] is not None}
    assert got == want
    appendix = {e["no"]: (e["title"], e["printed_page"])
                for e in tocs[2025] if e["level"] == 2 and e["chapter_no"] is None}
    assert appendix == {no: (title, page) for no, title, page in manual["appendix"]}


def _where(toc, page):
    found = toc_mod.chapter_of(toc, page)
    if found is None:
        return None
    return (found["chapter"]["label"], found["section"]["label"] if found["section"] else None)


@pytest.mark.parametrize("year,page,want", [
    (2020, 5, None), (2025, 3, None),
    (2020, 6, ("제1장", None)), (2020, 7, ("제1장", None)), (2021, 21, ("제2장", None)), (2025, 31, ("제2장", None)),
    (2020, 8, ("제1장", "제1절")), (2020, 20, ("제1장", "제1절")), (2020, 21, ("제1장", "제2절")),
    (2021, 6, ("제1장", None)), (2021, 7, ("제1장", "제1절")), (2021, 22, ("제2장", "제1절")),
    (2023, 395, ("부록", "부록 11")), (2025, 339, ("부록", "부록 11")), (2025, 274, ("부록", "부록 1")),
    (2024, 335, ("부록", "부록 8")), (2024, 336, ("부록", "부록 9")),
    (2020, 376, None), (2025, 340, None), (2022, 0, None),
])
def test_chapter_of(tocs, year, page, want):
    assert _where(tocs[year], page) == want
