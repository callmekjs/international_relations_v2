import json
import subprocess
import sys

import pytest

from assistant.corpus import Corpus
from assistant.search_index import build_index, save_index

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]


def _page(pid, year, printed, text, *, citable=True, printed_on_page=True, appendix=False):
    return {
        "page_id": pid, "year": year, "edition_title": f"{year}년도 국제정세와 외교활동",
        "pdf_page": int(pid[6:9]), "side": pid[-1], "single_page": False,
        "printed_page": printed, "label_printed": printed_on_page,
        "label_status": "detected" if printed_on_page else "inferred",
        "chapter_label": "부록" if appendix else "제2장", "chapter_title": "부록" if appendix else "한반도 평화",
        "section_label": "부록 1" if appendix else "제1절", "section_title": "주요 일지" if appendix else "북핵 문제",
        "is_appendix": appendix, "kind": "text" if citable else "image_only", "citable": citable, "text": text,
    }


@pytest.fixture()
def corpus_dir(tmp_path):
    pages = [
        _page("2023-p020L", 2023, 38, "한·미 정상회담이 열렸다.\n양국은 협력을 약속하였다."),
        _page("2023-p002R", 2023, 3, "인사말 본문", printed_on_page=False),
        _page("2023-p190L", 2023, 378, "2023년 한미 정상회담 일지", appendix=True),
        _page("2024-p020L", 2024, 38, "한미 정상회담 개최"),
        _page("2024-p004L", 2024, 6, "", citable=False),
    ]
    volumes = {"corpus_years": YEARS, "volumes": [
        {"year": 2023, "edition_title": "2023년도 국제정세와 외교활동", "file_name": "a.pdf"},
        {"year": 2024, "edition_title": "2024년도 국제정세와 외교활동", "file_name": "b.pdf"},
    ]}
    toc = {"2023": [{"level": 1, "label": "제2장", "no": 2, "title": "한반도 평화", "printed_page": 30,
                     "printed_end": 60}], "2024": []}
    (tmp_path / "volumes.json").write_text(json.dumps(volumes, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "toc.json").write_text(json.dumps(toc, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "missing.json").write_text("[]", encoding="utf-8")
    (tmp_path / "pages.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pages), encoding="utf-8")
    save_index(build_index([p for p in pages if p["citable"]]), tmp_path / "index")
    return tmp_path


def test_search_labels_chapters_and_appendix_flag(corpus_dir):
    result = Corpus(corpus_dir).search("한미 정상회담", years=[2023])
    hits = {h["page_id"]: h for h in result["hits"]}
    assert set(hits) == {"2023-p020L", "2023-p190L"}
    assert hits["2023-p020L"]["label"] == "2023년치 · 「2023년도 국제정세와 외교활동」 38쪽"
    assert hits["2023-p020L"]["chapter"] == "제2장 한반도 평화"
    assert hits["2023-p020L"]["section"] == "제1절 북핵 문제"
    assert hits["2023-p190L"]["is_appendix"] is True
    assert hits["2023-p190L"]["chapter"] == "부록"
    assert result["out_of_range_years"] == []


def test_search_reports_years_outside_the_corpus(corpus_dir):
    corpus = Corpus(corpus_dir)
    assert corpus.search("정상회담", years=[2015]) == {"hits": [], "order": "score", "out_of_range_years": [2015],
                                                    "corpus_years": YEARS}
    mixed = corpus.search("정상회담", years=[2015, 2024])
    assert [h["page_id"] for h in mixed["hits"]] == ["2024-p020L"]
    assert mixed["out_of_range_years"] == [2015]


def test_search_several_years_includes_each_year(corpus_dir):
    hits = Corpus(corpus_dir).search("한미 정상회담", years=[2023, 2024], k=2)["hits"]
    assert {h["year"] for h in hits} == {2023, 2024}


def test_read_pages_splits_paragraphs_and_flags_problems(corpus_dir):
    result = Corpus(corpus_dir).read_pages(["2023-p020L", "2024-p004L", "2099-p001L"])
    assert [p["page_id"] for p in result["pages"]] == ["2023-p020L"]
    assert result["pages"][0]["paragraphs"] == ["한·미 정상회담이 열렸다.", "양국은 협력을 약속하였다."]
    assert result["not_citable"] == ["2024-p004L"]
    assert result["not_found"] == ["2099-p001L"]


def test_unprinted_page_number_is_marked(corpus_dir):
    page = Corpus(corpus_dir).read_pages(["2023-p002R"])["pages"][0]
    assert page["label"] == "2023년치 · 「2023년도 국제정세와 외교활동」 3쪽(번호 미인쇄)"


def test_read_pages_limit(corpus_dir):
    with pytest.raises(ValueError):
        Corpus(corpus_dir).read_pages([f"2023-p{n:03d}L" for n in range(1, 7)])


def test_get_toc(corpus_dir):
    corpus = Corpus(corpus_dir)
    toc = corpus.get_toc(2023)
    assert toc["edition_title"] == "2023년도 국제정세와 외교활동"
    assert toc["entries"] == [{"level": 1, "label": "제2장", "title": "한반도 평화", "printed_page": 30, "printed_end": 60}]
    assert toc["missing"] == []
    assert corpus.get_toc(2019) == {"not_in_corpus": True, "year": 2019, "corpus_years": YEARS}


def test_assistant_does_not_import_pymupdf():
    code = "import sys, assistant.corpus; print('pymupdf' in sys.modules or 'fitz' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_pages_before_the_first_chapter_are_front_matter(qa_corpus):
    pages = {p["page_id"]: p for p in qa_corpus.read_pages(["2023-p002R", "2023-p020L", "2023-p190L"])["pages"]}
    assert pages["2023-p002R"]["front_matter"] is True
    assert pages["2023-p020L"]["front_matter"] is False
    assert pages["2023-p190L"]["front_matter"] is False


def test_label_is_only_for_citable_pages(qa_corpus):
    with pytest.raises(ValueError):
        qa_corpus.label(qa_corpus.pages["2024-p004L"])


def test_search_says_how_hits_are_ordered(qa_corpus):
    assert qa_corpus.search("한미 정상회담")["order"] == "score"
    assert qa_corpus.search("한미 정상회담", years=[2023])["order"] == "score"
    assert qa_corpus.search("한미 정상회담", years=[2023, 2024])["order"] == "year_turns"
    assert "front_matter" in qa_corpus.search("정상외교", years=[2023])["hits"][0]
