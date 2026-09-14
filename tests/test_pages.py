import pytest

from prep.pages import build_records
from prep.toc_build import build_toc

pytestmark = pytest.mark.pdf


@pytest.fixture(scope="module")
def records():
    return {year: build_records(year, build_toc(year)) for year in (2021, 2023, 2025)}


def _rec(records, pid):
    return next(r for r in records[int(pid[:4])] if r["page_id"] == pid)


def test_page_ids_unique(records):
    for rows in records.values():
        ids = [r["page_id"] for r in rows]
        assert len(ids) == len(set(ids))


def test_citable_pages_have_text_and_number(records):
    for rows in records.values():
        for r in rows:
            if r["citable"]:
                assert r["kind"] == "text", r["page_id"]
                assert r["text"].strip(), r["page_id"]
                assert r["printed_page"] is not None, r["page_id"]


def test_2021_first_section_page(records):
    r = _rec(records, "2021-p005L")
    assert r["citable"] and r["printed_page"] == 7 and r["label_printed"]
    assert (r["chapter_label"], r["section_label"], r["section_title"]) == ("제1장", "제1절", "국제정세 개관")
    assert r["text"].split("\n")[:2] == ["제1절", "국제정세 개관"]


def test_covers_dividers_colophons_not_citable(records):
    for pid in ("2021-p001L", "2021-p004L", "2021-p004R", "2021-p012L", "2021-p012R", "2021-p142L", "2023-p199L"):
        assert not _rec(records, pid)["citable"], pid


def test_2025_missing_halves_are_images_and_not_citable(records):
    for pid in ("2025-p002L", "2025-p002R", "2025-p003L", "2025-p003R", "2025-p138L", "2025-p138R"):
        r = _rec(records, pid)
        assert r["kind"] == "image_only" and not r["citable"], pid


def test_text_hygiene(records):
    for rows in records.values():
        for r in rows:
            for bad in ("\x07", "\x08", "­"):
                assert bad not in r["text"], (r["page_id"], repr(bad))
    assert "NATO" in _rec(records, "2023-p002R")["text"]


def test_appendix_flag(records):
    r = _rec(records, "2025-p170R")
    assert r["printed_page"] == 339
    assert r["is_appendix"] and r["section_label"] == "부록 11"


def test_most_halves_are_citable(records):
    counts = {year: sum(r["citable"] for r in rows) for year, rows in records.items()}
    assert counts[2021] > 240 and counts[2023] > 350 and counts[2025] > 290
