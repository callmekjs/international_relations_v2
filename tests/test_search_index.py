from assistant.search_index import build_index, load_index, save_index, search

PAGES = [
    {"page_id": "2023-p010L", "year": 2023, "text": "한·미 정상회담이 워싱턴에서 열렸다."},
    {"page_id": "2023-p011L", "year": 2023, "text": "한·아세안 협력을 강화하였다."},
    {"page_id": "2024-p010L", "year": 2024, "text": "한미 정상회담이 서울에서 열렸다."},
    {"page_id": "2024-p020R", "year": 2024, "text": "기후변화 대응 협력을 논의하였다."},
]


def _ids(hits):
    return [h["page_id"] for h in hits]


def test_finds_pages_regardless_of_spacing_and_dots():
    index = build_index(PAGES)
    assert set(_ids(search(index, "한미 정상회담")[:2])) == {"2023-p010L", "2024-p010L"}
    assert _ids(search(index, "한아세안"))[0] == "2023-p011L"


def test_year_filter():
    index = build_index(PAGES)
    assert _ids(search(index, "정상회담", years=[2024])) == ["2024-p010L"]


def test_balance_years_interleaves():
    index = build_index(PAGES)
    hits = search(index, "협력 정상회담", years=[2023, 2024], k=4, balance_years=True)
    assert [h["year"] for h in hits[:2]] == [2023, 2024]


def test_empty_and_unknown_queries_return_nothing():
    index = build_index(PAGES)
    assert search(index, "") == []
    assert search(index, "zzzz") == []


def test_snippet_shows_the_match():
    index = build_index(PAGES)
    assert "정상회담" in search(index, "정상회담", years=[2023])[0]["snippet"]


def test_save_and_load_give_same_results(tmp_path):
    index = build_index(PAGES)
    save_index(index, tmp_path / "index")
    loaded = load_index(tmp_path / "index")
    assert _ids(search(loaded, "한미 정상회담")) == _ids(search(index, "한미 정상회담"))
