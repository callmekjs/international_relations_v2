"""A tiny corpus/ folder for tests: real file formats, made-up sentences (no white-paper text)."""
from __future__ import annotations

import json
from pathlib import Path

from assistant.search_index import build_index, save_index

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]


def make_page(page_id: str, printed: int, text: str, *, chapter=("제2장", "한반도 평화"),
              section=("제1절", "북핵 문제"), appendix: bool = False, citable: bool = True,
              printed_on_page: bool = True) -> dict:
    year = int(page_id[:4])
    return {
        "page_id": page_id, "year": year, "edition_title": f"{year}년도 국제정세와 외교활동",
        "pdf_page": int(page_id[6:9]), "side": page_id[-1], "single_page": False,
        "printed_page": printed, "label_printed": printed_on_page,
        "label_status": "detected" if printed_on_page else "inferred",
        "chapter_label": chapter[0] if chapter else None, "chapter_title": chapter[1] if chapter else None,
        "section_label": section[0] if section else None, "section_title": section[1] if section else None,
        "is_appendix": appendix, "kind": "text" if citable else "image_only", "citable": citable, "text": text,
    }


QA_PAGES = [
    make_page("2023-p002R", 3, "인사말\n2023년 우리 외교는 새로운 도전 속에서도 정상외교의 폭을 넓혔습니다.",
              chapter=None, section=None, printed_on_page=False),
    make_page("2023-p020L", 38, "한\u00b7미 정상회담이 4월 26일 워싱턴에서 열렸다.\n"
                                "양국 정상은 확장억제 강화를 위한 워싱턴 선언을 채택하였다."),
    make_page("2023-p020R", 39, "8월 18일 캠프 데이비드에서 한미일 정상회의가 개최되었다.\n"
                                "3국 정상은 3자 협의 공약을 발표하였다."),
    make_page("2023-p190L", 378, "2023년 주요 외교 일지\n4.26 한\u00b7미 정상회담 (워싱턴)",
              chapter=("부록", "부록"), section=("부록 1", "주요 일지"), appendix=True),
    make_page("2024-p020L", 38, "한미 정상회담이 개최되었다.\n신속해외송금 지원 실적은 257건이었다."),
    make_page("2024-p004L", 6, "", citable=False),
]

QA_TOC = {
    "2023": [{"level": 1, "label": "제2장", "no": 2, "title": "한반도 평화", "printed_page": 30, "printed_end": 60}],
    "2024": [],
}


def write_corpus(directory: Path, pages: list[dict], toc: dict | None = None) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    years = sorted({page["year"] for page in pages})
    volumes = {"corpus_years": YEARS, "volumes": [
        {"year": year, "edition_title": f"{year}년도 국제정세와 외교활동", "file_name": f"{year}.pdf"}
        for year in years]}
    toc = toc if toc is not None else {str(year): [] for year in years}
    (directory / "volumes.json").write_text(json.dumps(volumes, ensure_ascii=False), encoding="utf-8")
    (directory / "toc.json").write_text(json.dumps(toc, ensure_ascii=False), encoding="utf-8")
    (directory / "missing.json").write_text("[]", encoding="utf-8")
    (directory / "pages.jsonl").write_text(
        "".join(json.dumps(page, ensure_ascii=False) + "\n" for page in pages), encoding="utf-8")
    save_index(build_index([page for page in pages if page["citable"]]), directory / "index")
    return directory
