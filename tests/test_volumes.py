import pytest

from prep.volumes import CORPUS_YEARS, MISSING, VOLUMES


def test_six_volumes_cover_2020_to_2025():
    assert CORPUS_YEARS == (2020, 2021, 2022, 2023, 2024, 2025)
    assert sorted(VOLUMES) == list(CORPUS_YEARS)


def test_edition_titles():
    assert VOLUMES[2020].edition_title == "2021 외교백서"
    for year in range(2021, 2026):
        assert VOLUMES[year].edition_title == f"{year}년도 국제정세와 외교활동"


def test_missing_entries_are_the_2025_images():
    assert [m["what"] for m in MISSING] == ["인사말", "목차", "부록 1 외교부 조직도"]
    assert {m["year"] for m in MISSING} == {2025}
    assert [m["pdf_pages"] for m in MISSING] == [[2], [3], [138]]


@pytest.mark.pdf
def test_pdf_files_exist():
    for vol in VOLUMES.values():
        assert vol.pdf_path.is_file(), vol.pdf_path
