import collections
import re

import pymupdf
import pytest

from prep import extract
from prep.pages import list_halves, page_id
from prep.volumes import VOLUMES

pytestmark = pytest.mark.pdf

HALF_COUNTS = {2020: 380, 2021: 284, 2022: 346, 2023: 397, 2024: 387, 2025: 342}


def test_page_id_format():
    assert page_id(2023, 50, "L") == "2023-p050L"


@pytest.fixture(scope="module")
def halves():
    return {year: list_halves(year) for year in HALF_COUNTS}


def _half(halves, year, pdf_page, side):
    return next(h for h in halves[year] if h["pdf_page"] == pdf_page and h["side"] == side)


def test_half_counts(halves):
    assert {year: len(rows) for year, rows in halves.items()} == HALF_COUNTS


@pytest.mark.parametrize("year,pdf_page,side,printed,status", [
    (2020, 50, "L", 96, "detected"),
    (2021, 5, "L", 7, "detected"),      # the folio printed here is one higher than the 목차
    (2021, 11, "R", 20, "detected"),
    (2021, 12, "L", 21, "inferred"),    # chapter-2 divider spread carries no number
    (2021, 13, "L", 22, "detected"),
    (2021, 50, "R", 97, "detected"),
    (2022, 5, "L", 8, "detected"),
    (2023, 50, "L", 98, "detected"),
    (2024, 6, "L", 10, "detected"),
    (2025, 2, "L", 2, "inferred"),
    (2025, 50, "R", 99, "detected"),
    (2025, 138, "L", 274, "detected"),
])
def test_printed_labels(halves, year, pdf_page, side, printed, status):
    half = _half(halves, year, pdf_page, side)
    assert (half["printed_page"], half["label_status"]) == (printed, status)


def test_covers_and_colophons(halves):
    assert _half(halves, 2020, 1, "L")["label_status"] == "cover"
    assert _half(halves, 2020, 190, "R")["label_status"] == "inferred_after_last"
    last_2023 = _half(halves, 2023, 199, "L")
    assert last_2023["single_page"] is True
    assert last_2023["label_status"] == "inferred_after_last"


@pytest.mark.parametrize("year,pdf_page", [(2020, 50), (2021, 13), (2022, 100), (2023, 50), (2024, 100), (2025, 50)])
def test_spread_split_keeps_every_character(year, pdf_page):
    path = str(VOLUMES[year].pdf_path)
    with pymupdf.open(path) as doc:
        full = collections.Counter(re.sub(r"\s", "", doc[pdf_page - 1].get_text("text")))
    halves_text = extract.extract_half_text(path, pdf_page, "L") + extract.extract_half_text(path, pdf_page, "R")
    assert collections.Counter(re.sub(r"\s", "", halves_text)) == full
