# 계획 1: 백서 준비 (코퍼스) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2020~2025년치 외교백서 6권을 `corpus/`로 만든다. `corpus/`에는 쪽 기록, 목차, 자료 없음 목록, 찾아보기 목록이 들어간다. 그리고 LLM 없이 찾기 · 쪽 읽기 · 목차 보기를 하는 `assistant.corpus.Corpus`를 만든다.

**Architecture:**
- `prep/`가 PDF를 반쪽(인쇄 1쪽) 단위로 읽어 `corpus/`에 파일로 쓴다.
- 쪽 번호 · 목차 · 글자 정리는 사전 조사에서 검증한 코드(`docs/research/2026-09-14-groundwork/prototypes/`)를 그대로 옮겨 쓴다. 그 위에 조립 코드와 시험을 붙인다.
- `assistant/`는 PyMuPDF 없이 `corpus/`만 읽는다. 나중에 Hugging Face Space에서 돌기 때문이다.

**Tech Stack:** Python 3.12, PyMuPDF 1.26.7(준비 단계만), bm25s 0.3.11 + numpy 2.5.3(찾기), pytest

**근거 문서:**
- 설계서: `docs/superpowers/specs/2026-09-14-whitepaper-ai-assistant-design.md` (2장 자료, 3장 구조, 4.1 도구, 8.1 시험)
- 사전 조사: `docs/research/2026-09-14-groundwork/README.md` (결정 D1~D10)

## Global Constraints

- 1차 자료는 `data/` 폴더 2020, 2021, 2022, 2023, 2024, 2025의 PDF 6권뿐이다. `data/`는 읽기만 한다.
- "○○년치" = 백서가 다룬 해 = `data/` 폴더 연도다.
- 판 이름: 2020 → 「2021 외교백서」, 2021~2025 → 「YYYY년도 국제정세와 외교활동」.
- 인용하는 쪽 번호는 **그 쪽에 찍힌 번호**다. 번호가 안 찍힌 쪽은 앞뒤로 채운 번호에 "번호 미인쇄"를 붙인다.
- `data/`, `corpus/`, `.venv/`는 git에 올리지 않는다(저작권 · 크기). `.gitignore`에 이미 들어 있다.
- 시험은 LLM(Claude API)을 부르지 않는다.
- PyMuPDF는 1.26.7로 고정한다. 쪽 번호 · 목차 규칙이 이 판에서 검증됐다.
- `assistant/` 코드는 PyMuPDF(`pymupdf`, `fitz`)를 import하지 않는다.
- 명령은 Git Bash에서 프로젝트 폴더(`/c/international_relations`)를 기준으로 실행한다. 한국어 출력이 깨지지 않게 `PYTHONUTF8=1`을 붙인다.
- 커밋 메시지는 `유형: 제목` 형식이다.
  - 유형은 feat / fix / docs / test / chore / refactor 중 하나다.
  - 제목은 영어 명령문 50자 이내, 첫 글자 대문자, 끝에 마침표 없음.
  - 제목과 본문 사이는 한 줄 띄우고, 본문에는 무엇을 왜 했는지 쓴다.
  - 마지막 줄은 `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`이다.
- 작업은 `feature/corpus-prep` 가지에서 한다. 끝나면 main에 합치고 push한 뒤 가지를 지운다(Task 9).
- 고친 문제가 있으면 `docs/에러노트.md`에 증상 · 원인 · 해결 · 배운 점을 적는다.

---

## 파일 구조

| 파일 | 하는 일 |
|---|---|
| `requirements.txt` | 앱 실행용 (bm25s, numpy) |
| `requirements-prep.txt` | 준비 · 시험용 (`-r requirements.txt` + pymupdf, pytest) |
| `pytest.ini` | 시험 설정, 표시 `pdf` · `slow` |
| `prep/__init__.py` | 빈 파일 |
| `prep/volumes.py` | 6권 목록(파일 이름 · 판 이름), 자료 범위, 자료 없음 목록 |
| `prep/extract.py` | 검증본 복사: 반쪽 글자 추출 · 정리, 반쪽 종류 판별 |
| `prep/running_strings.json` | 검증본 복사: 권마다 배운 머리글 · 바닥글 문자열 (`extract.py` 옆에 있어야 함) |
| `prep/toc.py` | 검증본 복사: 쪽 번호 `page_labels`, 목차 `extract_toc`, `chapter_of` |
| `prep/manual_toc_2025.json` | 검증본 복사: 사람이 옮긴 2025 목차 |
| `prep/toc_build.py` | 권마다 목차 만들기 + 2025 제목 보정 |
| `prep/pages.py` | 반쪽 목록과 쪽 기록 만들기 |
| `prep/build.py` | `python -m prep.build`: `corpus/` 전체 만들기 |
| `assistant/__init__.py` | 빈 파일 |
| `assistant/textnorm.py` | 찾기 · 대조용 글자 정규화, bigram 토큰 |
| `assistant/search_index.py` | bigram BM25 찾아보기 목록: 만들기 · 찾기 · 저장 · 불러오기 |
| `assistant/corpus.py` | `Corpus`: 찾기 · 쪽 읽기 · 목차 보기 |
| `tests/conftest.py` | PDF가 없으면 `pdf` 시험 건너뛰기, 6권 코퍼스 한 번 만들기 |
| `tests/test_*.py` | 시험 (Task마다) |
| `tests/fixtures/search_queries.jsonl` | 사전 조사 검증 42문항 복사본 |

## corpus 파일 형식 (이 계획이 정하는 약속)

`corpus/volumes.json`
```json
{"corpus_years": [2020, 2021, 2022, 2023, 2024, 2025],
 "volumes": [{"year": 2020, "edition_title": "2021 외교백서", "file_name": "2021 외교백서(국문).pdf"}]}
```

`corpus/pages.jsonl`: 한 줄에 반쪽 하나다. 인용하지 않는 반쪽도 `citable: false`로 들어간다.
```json
{"page_id": "2023-p050L", "year": 2023, "edition_title": "2023년도 국제정세와 외교활동",
 "pdf_page": 50, "side": "L", "single_page": false,
 "printed_page": 98, "label_printed": true, "label_status": "detected",
 "chapter_label": "제3장", "chapter_title": "…", "section_label": "제2절", "section_title": "…",
 "is_appendix": false, "kind": "text", "citable": true, "text": "문단 하나\n문단 둘"}
```
- `side`: 한 쪽짜리 PDF 쪽도 `"L"`이고, 이때 `single_page`가 `true`다.
- `label_status`: `detected`(번호가 찍힘) · `inferred`(앞뒤로 채움) · `cover` · `inferred_after_last`(판권 · 뒤표지) · `null`.
- `kind`: `text` · `little_text` · `image_only` · `blank` · `no_half`.
- `text`: 문단(또는 표 칸 · 제목)마다 한 줄이다. 인용하지 않는 반쪽은 빈 문자열이다.

`corpus/toc.json`: `{"2020": [항목, …], …}`. 항목은 `prep.toc.extract_toc`가 돌려주는 dict다. 키는 `level`, `label`, `no`, `chapter_no`, `title`, `printed_page`, `printed_end`, `toc_page`, `pdf_page`, `divider` 등이다.

`corpus/missing.json`: `prep.volumes.MISSING` 가운데 만든 해의 항목 목록이다.

`corpus/index/`: `bm25s/`(bm25s 저장 파일)와 `meta.json`(`page_ids`, `years`, 한 줄로 정규화한 `texts`)이다.

---

### Task 1: 준비 환경과 6권 목록

**Files:**
- Create: `requirements.txt`, `requirements-prep.txt`, `pytest.ini`, `prep/__init__.py`, `assistant/__init__.py`, `prep/volumes.py`, `tests/conftest.py`
- Test: `tests/test_volumes.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `prep.volumes.ROOT: Path` (프로젝트 폴더), `DATA_DIR: Path`
  - `CORPUS_YEARS: tuple[int, ...] = (2020, …, 2025)`
  - `Volume(year: int, file_name: str, edition_title: str)`, 속성 `pdf_path: Path`
  - `VOLUMES: dict[int, Volume]`
  - `MISSING: tuple[dict, ...]` (각 항목 키: `year`, `what`, `pdf_pages: list[int]`, `printed_from`, `printed_to`, `reason`)

- [ ] **Step 1: 작업 가지를 만든다**

```bash
cd /c/international_relations
git checkout main
git checkout -b feature/corpus-prep
git branch --show-current
```
Expected: `feature/corpus-prep`

- [ ] **Step 2: 가상환경과 의존성 파일을 만든다**

`requirements.txt`:
```text
bm25s==0.3.11
numpy==2.5.3
```

`requirements-prep.txt`:
```text
-r requirements.txt
pymupdf==1.26.7
pytest
```

설치:
```bash
/c/Users/anyca/AppData/Local/Programs/Python/Python312/python.exe -m venv .venv
.venv/Scripts/python -m pip install -r requirements-prep.txt
.venv/Scripts/python -c "import pymupdf, bm25s, numpy; print(pymupdf.version[0], bm25s.__version__, numpy.__version__)"
```
Expected: `1.26.7 0.3.11 2.5.3`

- [ ] **Step 3: 실패하는 시험을 쓴다**

`pytest.ini`:
```ini
[pytest]
testpaths = tests
markers =
    pdf: 백서 PDF(data/)가 있어야 도는 시험
    slow: 6권 코퍼스를 통째로 만드는 시험 (몇 분 걸림)
```

`tests/test_volumes.py`:
```python
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


def test_pdf_files_exist():
    for vol in VOLUMES.values():
        assert vol.pdf_path.is_file(), vol.pdf_path
```

- [ ] **Step 4: 시험이 실패하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_volumes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prep'`

- [ ] **Step 5: 구현한다**

`prep/__init__.py`, `assistant/__init__.py`: 빈 파일.

`prep/volumes.py`:
```python
"""The six first-phase volumes (data folders 2020-2025) and fixed facts about them."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CORPUS_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


@dataclass(frozen=True)
class Volume:
    year: int  # the year the volume covers = data folder name
    file_name: str
    edition_title: str

    @property
    def pdf_path(self) -> Path:
        return DATA_DIR / str(self.year) / self.file_name


VOLUMES = {
    2020: Volume(2020, "2021 외교백서(국문).pdf", "2021 외교백서"),
    2021: Volume(2021, "2021년도 국제정세와 외교활동(외교백서)_홈페이지 게시.pdf", "2021년도 국제정세와 외교활동"),
    2022: Volume(2022, "2022년도 국제정세와 외교활동(외교백서).pdf", "2022년도 국제정세와 외교활동"),
    2023: Volume(2023, "2023년도 국제정세와 외교활동.pdf", "2023년도 국제정세와 외교활동"),
    2024: Volume(2024, "2024년도 국제정세와 외교활동.pdf", "2024년도 국제정세와 외교활동"),
    2025: Volume(2025, "2025년도 국제정세와 외교활동.pdf", "2025년도 국제정세와 외교활동"),
}

# Real content that exists only as an image (confirmed on renders by two agents, 2026-09-14).
# Chapter divider images are not listed: they only repeat chapter titles already in the toc.
MISSING = (
    {"year": 2025, "what": "인사말", "pdf_pages": [2], "printed_from": 2, "printed_to": 3,
     "reason": "그림으로만 들어 있음"},
    {"year": 2025, "what": "목차", "pdf_pages": [3], "printed_from": 4, "printed_to": 5,
     "reason": "그림으로만 들어 있음 (목차는 본문 제목으로 복원)"},
    {"year": 2025, "what": "부록 1 외교부 조직도", "pdf_pages": [138], "printed_from": 274, "printed_to": 275,
     "reason": "그림으로만 들어 있음"},
)
```

`tests/conftest.py`:
```python
import pytest

from prep.volumes import VOLUMES


def _pdfs_present() -> bool:
    return all(vol.pdf_path.is_file() for vol in VOLUMES.values())


def pytest_collection_modifyitems(config, items):
    if _pdfs_present():
        return
    skip = pytest.mark.skip(reason="data/ 폴더에 백서 PDF가 없음")
    for item in items:
        if "pdf" in item.keywords:
            item.add_marker(skip)
```

- [ ] **Step 6: 시험이 통과하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_volumes.py -v`
Expected: 4 passed

- [ ] **Step 7: 커밋한다**

```bash
git add requirements.txt requirements-prep.txt pytest.ini prep/__init__.py prep/volumes.py assistant/__init__.py tests/conftest.py tests/test_volumes.py
git status --short
git commit -F - <<'EOF'
feat: Add volume registry and test setup

List the six 2020-2025 white papers with file names, edition titles
and the three 2025 parts that exist only as images, so every later
step reads the same facts. Pin PyMuPDF 1.26.7 and bm25s 0.3.11, the
versions the groundwork was verified with.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```
Expected: `git status --short`에 `.venv`, `data`, `corpus`가 보이지 않는다.

---

### Task 2: 검증된 추출 · 쪽 번호 코드 옮기기와 반쪽 목록

**Files:**
- Create (복사): `prep/extract.py`, `prep/running_strings.json`, `prep/toc.py`, `prep/manual_toc_2025.json`
- Create: `prep/pages.py`
- Test: `tests/test_halves.py`

**Interfaces:**
- Consumes: `prep.volumes.VOLUMES`
- Produces:
  - `prep.pages.page_id(year: int, pdf_page: int, side: str) -> str` (예: `"2023-p050L"`)
  - `prep.pages.list_halves(year: int) -> list[dict]`. 반쪽마다 `year`, `pdf_page`(1부터), `side`(`"L"`/`"R"`), `single_page: bool`, `printed_page: int | None`, `label_status: str | None`
  - 복사한 모듈의 공개 함수 (검증본 그대로):
    - `prep.extract.extract_half_text(pdf_path: str, pdf_page: int, side: str, *, running: bool = True) -> str`
    - `prep.extract.clean_text(text: str, volume_year: int) -> str`
    - `prep.extract.classify_half(pdf_path: str, pdf_page: int, side: str) -> dict` (`kind` 키)
    - `prep.toc.page_labels(doc) -> tuple[list[dict], list[dict], list[dict]]` (라벨, 상태, 이상)
    - `prep.toc.extract_toc(pdf_path: str, year: int, prefer: str | None = None) -> list[dict]`
    - `prep.toc.chapter_of(toc: list[dict], printed_page: int | None) -> dict | None`

- [ ] **Step 1: 검증본을 복사하고, 절대 경로가 든 실행 블록을 지운다**

```bash
R=docs/research/2026-09-14-groundwork
cp $R/prototypes/extract.py $R/prototypes/running_strings.json $R/prototypes/toc.py prep/
cp $R/fixtures/manual_toc_2025.json prep/
PYTHONUTF8=1 .venv/Scripts/python - <<'EOF'
from pathlib import Path
path = Path("prep/toc.py")
source = path.read_text(encoding="utf-8")
cut = source.index("\nif __name__ == '__main__':")
path.write_text(source[:cut].rstrip() + "\n", encoding="utf-8")
EOF
tail -3 prep/toc.py
```
Expected: 마지막 줄이 `    return {'chapter': ch, 'section': sec}`이다.

- [ ] **Step 2: 실패하는 시험을 쓴다**

`tests/test_halves.py`:
```python
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
```

- [ ] **Step 3: 시험이 실패하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_halves.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prep.pages'`

- [ ] **Step 4: 구현한다**

`prep/pages.py`:
```python
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
```

- [ ] **Step 5: 시험이 통과하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_halves.py -v`
Expected: 21 passed (1분 안쪽)

- [ ] **Step 6: 커밋한다**

```bash
git add prep/extract.py prep/running_strings.json prep/toc.py prep/manual_toc_2025.json prep/pages.py tests/test_halves.py
git commit -F - <<'EOF'
feat: Import verified extraction and page labels

Copy the extraction, page-label and toc code that the groundwork
verified on all 2,136 halves, and list halves with the folio actually
printed on each page. Tests pin the 2021 chapter-1 folios, covers,
colophons and the lossless split of two-page spreads.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 3: 목차 만들기 (2025 제목 보정 포함)

**Files:**
- Create: `prep/toc_build.py`
- Test: `tests/test_toc_build.py`

**Interfaces:**
- Consumes: `prep.toc.extract_toc`, `prep.toc.chapter_of`, `prep.volumes.VOLUMES`
- Produces:
  - `prep.toc_build.build_toc(year: int) -> list[dict]`: `extract_toc` 결과. 2025는 제목을 손으로 옮긴 목차로 바꾼다.
  - `prep.toc_build.apply_manual_titles(entries: list[dict], manual: dict) -> None`: 제자리에서 제목만 바꾼다.

- [ ] **Step 1: 실패하는 시험을 쓴다**

`tests/test_toc_build.py`:
```python
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
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_toc_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prep.toc_build'`

- [ ] **Step 3: 구현한다**

`prep/toc_build.py`:
```python
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
```

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_toc_build.py -v`
Expected: 24 passed

- [ ] **Step 5: 커밋한다**

```bash
git add prep/toc_build.py tests/test_toc_build.py
git commit -F - <<'EOF'
feat: Build per-volume table of contents

Use the verified toc extraction for all six volumes and take 2025
titles from the hand transcription because its printed 목차 is an
image. Tests pin section counts, the 2021 folio shift and chapter
lookups at divider, boundary and past-the-end pages.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 4: 쪽 기록 만들기

**Files:**
- Modify: `prep/pages.py` (`build_records` 추가)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `prep.pages.list_halves`, `prep.pages.page_id`, `prep.extract.classify_half` · `extract_half_text` · `clean_text`, `prep.toc.chapter_of`, `prep.volumes.MISSING` · `VOLUMES`
- Produces: `prep.pages.build_records(year: int, toc: list[dict]) -> list[dict]`. 반쪽마다 위 "corpus 파일 형식"의 `pages.jsonl` 한 줄과 같은 dict를 돌려준다.

인용 규칙(`citable`)은 아래를 **모두** 만족할 때 참이다.
1. `kind == "text"`이고 정리한 글자가 비어 있지 않음
2. `label_status`가 `detected` 또는 `inferred`
3. 자료 없음 목록(`MISSING`)의 PDF 쪽이 아님
4. 목차의 장 간지(`divider`)가 아님

- [ ] **Step 1: 실패하는 시험을 쓴다**

`tests/test_pages.py`:
```python
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
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_pages.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_records' from 'prep.pages'`

- [ ] **Step 3: 구현한다**

`prep/pages.py`의 import를 바꾸고, 파일 끝에 함수를 덧붙인다.

import 부분: `from __future__ import annotations` 아래에 있는 기존 세 줄(`import pymupdf`, `from prep import toc as toc_mod`, `from prep.volumes import VOLUMES`)을 통째로 아래 블록으로 바꾼다.
```python
import pymupdf

from prep import extract
from prep import toc as toc_mod
from prep.volumes import MISSING, VOLUMES

CITABLE_STATUS = {"detected", "inferred"}
```

파일 끝에 덧붙이는 함수:
```python
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
```

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_pages.py -v`
Expected: 8 passed

- [ ] **Step 5: 앞 Task 시험도 함께 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_volumes.py tests/test_halves.py tests/test_toc_build.py tests/test_pages.py -q`
Expected: 모두 passed

- [ ] **Step 6: 커밋한다**

```bash
git add prep/pages.py tests/test_pages.py
git commit -F - <<'EOF'
feat: Build page records with citable flags

Turn each half into a record with its printed folio, chapter and
section, kind and cleaned text. Covers, chapter dividers, colophons
and the image-only 2025 parts are kept but marked not citable, so
search and read_pages never point readers at them.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 5: 찾기용 정규화와 bigram 찾아보기 목록

**Files:**
- Create: `assistant/textnorm.py`, `assistant/search_index.py`
- Test: `tests/test_textnorm.py`, `tests/test_search_index.py` (PDF 필요 없음)

**Interfaces:**
- Consumes: 없음 (PyMuPDF 쓰지 않음)
- Produces:
  - `assistant.textnorm.normalize(text: str) -> str`: 한 줄로 정규화
  - `assistant.textnorm.match_key(text: str) -> str`: 대조용 (공백 없음, 한글 사이 `·` 없음, 소문자)
  - `assistant.textnorm.bigram_tokens(text: str) -> list[str]`
  - `assistant.search_index.SearchIndex` (dataclass: `page_ids: list[str]`, `years: np.ndarray`, `texts: list[str]`, `engine: bm25s.BM25`)
  - `assistant.search_index.build_index(pages: list[dict]) -> SearchIndex` (각 dict에 `page_id`, `year`, `text`)
  - `assistant.search_index.search(index, query: str, years: list[int] | None = None, k: int = 10, balance_years: bool = False) -> list[dict]` (각 결과: `page_id`, `year`, `rank`, `score`, `snippet`)
  - `assistant.search_index.save_index(index, directory: Path) -> None`, `load_index(directory: Path) -> SearchIndex`

- [ ] **Step 1: 실패하는 시험을 쓴다**

`tests/test_textnorm.py`:
```python
from assistant.textnorm import bigram_tokens, match_key, normalize


def test_dot_variants_become_middle_dot():
    for variant in ("ㆍ", "･", "・", "‧", "∙", "․", "·", ""):
        assert normalize(f"한{variant}미") == "한·미"


def test_soft_hyphen_and_invisible_characters_removed():
    assert normalize("NA­\nTO 정상회의") == "NATO 정상회의"
    assert normalize("발행처\x07 외교부​") == "발행처 외교부"


def test_whitespace_collapsed_to_one_line():
    assert normalize("첫 줄\n둘째　줄\t끝") == "첫 줄 둘째 줄 끝"


def test_match_key_ignores_spaces_and_hangul_dots():
    assert match_key("한·아세안 협력") == match_key("한아세안협력") == "한아세안협력"
    assert match_key("G20 정상회의") == "g20정상회의"


def test_bigram_tokens():
    assert bigram_tokens("정상 회담") == ["정상", "상회", "회담"]
    assert bigram_tokens("한·아세안") == bigram_tokens("한아세안") == ["한아", "아세", "세안"]
    assert bigram_tokens("G20 정상회의 2023") == ["g", "20", "정상", "상회", "회의", "2023"]
    assert bigram_tokens("미") == ["미"]
    assert bigram_tokens("") == []
```

`tests/test_search_index.py`:
```python
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
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_textnorm.py tests/test_search_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'assistant.textnorm'`

- [ ] **Step 3: 구현한다**

`assistant/textnorm.py`:
```python
"""Character normalisation shared by search now and by the table/compare cell check later."""
from __future__ import annotations

import re
import unicodedata

_SOFT_HYPHEN = re.compile("­\n?")
_INVISIBLE = re.compile("[\x07\x08​‌‍﻿]")
_SPACES = re.compile("[　 \t]")
_DOTS = re.compile("[ㆍ・･‧∙⋅•․·]")
_HANGUL_GAP = re.compile(r"(?<=[가-힣])[\s·]+(?=[가-힣])")
_RUNS = re.compile(r"[가-힣]+|[一-鿿]+|[a-z]+|\d+")
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFC; soft hyphens and invisible characters removed; dot variants unified to '·';
    all whitespace collapsed to single spaces (one line, for snippets)."""
    t = unicodedata.normalize("NFC", text or "")
    t = _SOFT_HYPHEN.sub("", t)
    t = _INVISIBLE.sub("", t)
    t = _SPACES.sub(" ", t)
    t = _DOTS.sub("·", t)
    return _WS.sub(" ", t).strip()


def match_key(text: str) -> str:
    """Comparison form: normalized, lower-cased, no whitespace, no '·' between Hangul."""
    return _WS.sub("", _HANGUL_GAP.sub("", normalize(text).lower()))


def bigram_tokens(text: str) -> list[str]:
    """Hangul/Hanja runs become character bigrams (a one-character run stays whole); Latin words
    and numbers stay whole. Spaces and '·' between Hangul are removed first, so '한·미 정상'
    and '한미정상' tokenize the same (groundwork D7, D8)."""
    t = _HANGUL_GAP.sub("", normalize(text).lower())
    tokens: list[str] = []
    for match in _RUNS.finditer(t):
        run = match.group(0)
        if "가" <= run[0] <= "힣" or "一" <= run[0] <= "鿿":
            tokens.extend([run] if len(run) == 1 else [run[i:i + 2] for i in range(len(run) - 1)])
        else:
            tokens.append(run)
    return tokens
```

`assistant/search_index.py`:
```python
"""Page-level BM25 over character bigrams (bm25s), chosen in the 2026-09-14 groundwork (D7)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import bm25s
import numpy as np

from assistant.textnorm import bigram_tokens, normalize

K1 = 1.5
B = 0.75
SNIPPET_WIDTH = 150
_WORDS = re.compile(r"[\w·]+")


@dataclass
class SearchIndex:
    page_ids: list[str]
    years: np.ndarray
    texts: list[str]  # normalized one-line page text, for snippets
    engine: bm25s.BM25


def build_index(pages: list[dict]) -> SearchIndex:
    """pages: rows with page_id, year and text. Pass only citable pages."""
    if not pages:
        raise ValueError("no pages to index")
    engine = bm25s.BM25(k1=K1, b=B, method="lucene")
    engine.index([bigram_tokens(p["text"]) for p in pages], show_progress=False)
    return SearchIndex(
        page_ids=[p["page_id"] for p in pages],
        years=np.array([int(p["year"]) for p in pages], dtype=np.int32),
        texts=[normalize(p["text"]) for p in pages],
        engine=engine,
    )


def search(index: SearchIndex, query: str, years: list[int] | None = None, k: int = 10,
           balance_years: bool = False) -> list[dict]:
    """Top-k pages. years filters by covered year. balance_years interleaves the per-year
    rankings so every requested year is represented (groundwork D9)."""
    tokens = bigram_tokens(query)
    if not tokens or k <= 0:
        return []
    scores = np.asarray(index.engine.get_scores(tokens), dtype=np.float32)
    wanted = sorted(set(years)) if years else []
    if balance_years and len(wanted) > 1:
        per_year = [_top(scores, index.years == year, k) for year in wanted]
        hits: list[tuple[int, float]] = []
        rank = 0
        while len(hits) < k and any(rank < len(ranked) for ranked in per_year):
            for ranked in per_year:
                if rank < len(ranked) and len(hits) < k:
                    hits.append(ranked[rank])
            rank += 1
    else:
        hits = _top(scores, np.isin(index.years, wanted) if wanted else None, k)
    return [{"page_id": index.page_ids[i], "year": int(index.years[i]), "rank": n, "score": round(score, 4),
             "snippet": _snippet(index.texts[i], query)}
            for n, (i, score) in enumerate(hits, 1)]


def _top(scores: np.ndarray, mask: np.ndarray | None, k: int) -> list[tuple[int, float]]:
    s = scores.copy()
    if mask is not None:
        s[~mask] = -np.inf
    order = np.argsort(-s, kind="stable")[:k]
    return [(int(i), float(s[i])) for i in order if s[i] > 0]


def _snippet(text: str, query: str, width: int = SNIPPET_WIDTH) -> str:
    """About `width` characters around the first query word found (page start if none)."""
    words = sorted({w for w in _WORDS.findall(normalize(query)) if len(w) >= 2}, key=len, reverse=True)
    pos = -1
    for word in words:
        candidates = (word, word[:-1]) if len(word) >= 3 else (word,)
        for candidate in candidates:
            pos = text.find(candidate)
            if pos >= 0:
                break
        if pos >= 0:
            break
    start = max(0, pos - width // 3) if pos >= 0 else 0
    return text[start:start + width]


def save_index(index: SearchIndex, directory: Path) -> None:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    index.engine.save(str(directory / "bm25s"), show_progress=False)
    meta = {"tokenizer": "bigram", "k1": K1, "b": B, "page_ids": index.page_ids,
            "years": index.years.tolist(), "texts": index.texts}
    (directory / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def load_index(directory: Path) -> SearchIndex:
    directory = Path(directory)
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    engine = bm25s.BM25.load(str(directory / "bm25s"), show_progress=False)
    return SearchIndex(meta["page_ids"], np.array(meta["years"], dtype=np.int32), meta["texts"], engine)
```

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_textnorm.py tests/test_search_index.py -v`
Expected: 11 passed

- [ ] **Step 5: 커밋한다**

```bash
git add assistant/textnorm.py assistant/search_index.py tests/test_textnorm.py tests/test_search_index.py
git commit -F - <<'EOF'
feat: Add bigram BM25 search index

Search pages with character-bigram BM25, which beat Kiwi morphemes in
the six-volume check, after unifying dot variants and removing soft
hyphens and control characters. Multi-year searches interleave years
so one volume cannot fill every result slot.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 6: `corpus/` 만들기 (`python -m prep.build`)

**Files:**
- Create: `prep/build.py`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `prep.toc_build.build_toc`, `prep.pages.build_records`, `assistant.search_index.build_index` · `save_index`, `prep.volumes.CORPUS_YEARS` · `MISSING` · `ROOT` · `VOLUMES`
- Produces:
  - `prep.build.build(out_dir: Path, years: list[int]) -> dict`: `corpus` 파일을 쓰고 통계를 돌려준다(`years`, `halves`, `citable`, `citable_by_year`).
  - 명령 `python -m prep.build [--out DIR] [--years Y ...]`

- [ ] **Step 1: 실패하는 시험을 쓴다**

`tests/test_build.py`:
```python
import json

import pytest

from assistant.search_index import load_index, search
from prep.build import build

pytestmark = pytest.mark.pdf


def test_build_one_volume(tmp_path):
    stats = build(tmp_path, [2022])
    assert stats["halves"] == 346
    assert stats["citable"] > 300
    for name in ("volumes.json", "toc.json", "missing.json", "pages.jsonl", "index/meta.json"):
        assert (tmp_path / name).is_file(), name
    volumes = json.loads((tmp_path / "volumes.json").read_text(encoding="utf-8"))
    assert volumes["corpus_years"] == [2020, 2021, 2022, 2023, 2024, 2025]
    assert [v["year"] for v in volumes["volumes"]] == [2022]
    assert json.loads((tmp_path / "missing.json").read_text(encoding="utf-8")) == []
    rows = [json.loads(line) for line in (tmp_path / "pages.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 346
    hits = search(load_index(tmp_path / "index"), "정상회담", years=[2022])
    assert hits and all(h["year"] == 2022 for h in hits)
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prep.build'`

- [ ] **Step 3: 구현한다**

`prep/build.py`:
```python
"""Build corpus/ from the six PDFs.

    PYTHONUTF8=1 .venv/Scripts/python -m prep.build [--out corpus] [--years 2020 2021 ...]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from assistant.search_index import build_index, save_index
from prep.pages import build_records
from prep.toc_build import build_toc
from prep.volumes import CORPUS_YEARS, MISSING, ROOT, VOLUMES


def build(out_dir: Path, years: list[int]) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tocs: dict[str, list[dict]] = {}
    pages: list[dict] = []
    for year in years:
        tocs[str(year)] = build_toc(year)
        pages.extend(build_records(year, tocs[str(year)]))
    _write_json(out_dir / "volumes.json", {
        "corpus_years": list(CORPUS_YEARS),
        "volumes": [{"year": y, "edition_title": VOLUMES[y].edition_title, "file_name": VOLUMES[y].file_name}
                    for y in years],
    })
    _write_json(out_dir / "toc.json", tocs)
    _write_json(out_dir / "missing.json", [item for item in MISSING if item["year"] in years])
    with open(out_dir / "pages.jsonl", "w", encoding="utf-8") as f:
        for row in pages:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    citable = [p for p in pages if p["citable"]]
    save_index(build_index(citable), out_dir / "index")
    return {
        "years": list(years),
        "halves": len(pages),
        "citable": len(citable),
        "citable_by_year": {str(y): sum(p["citable"] for p in pages if p["year"] == y) for y in years},
    }


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build corpus/ from the white paper PDFs")
    parser.add_argument("--out", type=Path, default=ROOT / "corpus")
    parser.add_argument("--years", type=int, nargs="+", default=list(CORPUS_YEARS))
    args = parser.parse_args()
    started = time.time()
    stats = build(args.out, args.years)
    stats["seconds"] = round(time.time() - started, 1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_build.py -v`
Expected: 1 passed

- [ ] **Step 5: 커밋한다**

```bash
git add prep/build.py tests/test_build.py
git commit -F - <<'EOF'
feat: Add corpus build command

Write volumes, toc, missing, page records and the search index to
corpus/ in one command, so the app can later load prepared files
without PyMuPDF. The corpus folder stays out of git for copyright.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 7: `Corpus` — 찾기 · 쪽 읽기 · 목차 보기

**Files:**
- Create: `assistant/corpus.py`
- Test: `tests/test_corpus.py` (PDF 필요 없음, 작은 가짜 코퍼스 사용)

**Interfaces:**
- Consumes: `corpus/` 파일 형식 (위 약속), `assistant.search_index.load_index` · `search`
- Produces (계획 2에서 Claude 도구로 감쌀 함수):
  - `Corpus(directory: Path)`: 속성 `corpus_years: list[int]`, `volumes: dict[int, dict]`, `toc: dict[int, list[dict]]`, `missing: list[dict]`, `pages: dict[str, dict]`, `index`
  - `Corpus.label(page: dict) -> str`: `"2023년치 · 「2023년도 국제정세와 외교활동」 98쪽"` 또는 `"… 3쪽(번호 미인쇄)"`
  - `Corpus.search(query: str, years: list[int] | None = None, k: int = 10) -> dict`: `{"hits": [{page_id, label, year, chapter, section, is_appendix, snippet, score}], "out_of_range_years": [...], "corpus_years": [...]}`
  - `Corpus.read_pages(page_ids: list[str]) -> dict`: `{"pages": [{page_id, label, year, chapter, section, is_appendix, paragraphs}], "not_found": [...], "not_citable": [...]}`. 5쪽을 넘으면 `ValueError`
  - `Corpus.get_toc(year: int) -> dict`: `{"year", "edition_title", "entries": [{level, label, title, printed_page, printed_end}], "missing": [...]}` 또는 `{"not_in_corpus": True, "year", "corpus_years"}`
  - `assistant.corpus.MAX_READ_PAGES = 5`

- [ ] **Step 1: 실패하는 시험을 쓴다**

`tests/test_corpus.py`:
```python
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
    assert corpus.search("정상회담", years=[2015]) == {"hits": [], "out_of_range_years": [2015], "corpus_years": YEARS}
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
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_corpus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'assistant.corpus'`

- [ ] **Step 3: 구현한다**

`assistant/corpus.py`:
```python
"""Read-only access to corpus/ for the assistant tools (no PyMuPDF, no LLM)."""
from __future__ import annotations

import json
from pathlib import Path

from assistant.search_index import load_index
from assistant.search_index import search as search_index

MAX_READ_PAGES = 5


class Corpus:
    def __init__(self, directory: Path):
        directory = Path(directory)
        volumes = _read_json(directory / "volumes.json")
        self.corpus_years: list[int] = volumes["corpus_years"]
        self.volumes: dict[int, dict] = {v["year"]: v for v in volumes["volumes"]}
        self.toc: dict[int, list[dict]] = {int(y): entries for y, entries in _read_json(directory / "toc.json").items()}
        self.missing: list[dict] = _read_json(directory / "missing.json")
        with open(directory / "pages.jsonl", encoding="utf-8") as f:
            self.pages: dict[str, dict] = {row["page_id"]: row for row in map(json.loads, f)}
        self.index = load_index(directory / "index")

    def label(self, page: dict) -> str:
        number = f"{page['printed_page']}쪽" + ("" if page["label_printed"] else "(번호 미인쇄)")
        return f"{page['year']}년치 · 「{page['edition_title']}」 {number}"

    def search(self, query: str, years: list[int] | None = None, k: int = 10) -> dict:
        wanted = sorted(set(years or []))
        outside = [y for y in wanted if y not in self.corpus_years]
        inside = [y for y in wanted if y in self.corpus_years]
        if wanted and not inside:
            return {"hits": [], "out_of_range_years": outside, "corpus_years": self.corpus_years}
        hits = search_index(self.index, query, inside or None, k, balance_years=len(inside) > 1)
        return {"hits": [self._hit(h) for h in hits], "out_of_range_years": outside,
                "corpus_years": self.corpus_years}

    def read_pages(self, page_ids: list[str]) -> dict:
        if len(page_ids) > MAX_READ_PAGES:
            raise ValueError(f"한 번에 최대 {MAX_READ_PAGES}쪽까지 읽을 수 있습니다")
        pages, not_found, not_citable = [], [], []
        for pid in page_ids:
            page = self.pages.get(pid)
            if page is None:
                not_found.append(pid)
            elif not page["citable"]:
                not_citable.append(pid)
            else:
                pages.append({**self._where(page),
                              "paragraphs": [line for line in page["text"].split("\n") if line.strip()]})
        return {"pages": pages, "not_found": not_found, "not_citable": not_citable}

    def get_toc(self, year: int) -> dict:
        if year not in self.toc:
            return {"not_in_corpus": True, "year": year, "corpus_years": self.corpus_years}
        entries = [{"level": e["level"], "label": e["label"], "title": e["title"],
                    "printed_page": e.get("printed_page"), "printed_end": e.get("printed_end")}
                   for e in self.toc[year]]
        return {"year": year, "edition_title": self.volumes[year]["edition_title"], "entries": entries,
                "missing": [m for m in self.missing if m["year"] == year]}

    def _hit(self, hit: dict) -> dict:
        return {**self._where(self.pages[hit["page_id"]]), "snippet": hit["snippet"], "score": hit["score"]}

    def _where(self, page: dict) -> dict:
        return {
            "page_id": page["page_id"],
            "label": self.label(page),
            "year": page["year"],
            "chapter": _join(page["chapter_label"], page["chapter_title"]),
            "section": _join(page["section_label"], page["section_title"]),
            "is_appendix": page["is_appendix"],
        }


def _join(label: str | None, title: str | None) -> str | None:
    if not label:
        return None
    return f"{label} {title}" if title and title != label else label


def _read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_corpus.py -v`
Expected: 8 passed

- [ ] **Step 5: 커밋한다**

```bash
git add assistant/corpus.py tests/test_corpus.py
git commit -F - <<'EOF'
feat: Add corpus access for search, read and toc

Give the assistant tools one read-only entry point over corpus/ with
citation labels that use the printed folio, paragraph lists for
citable blocks, a five-page read limit and explicit reports for years
outside 2020-2025. It loads without PyMuPDF for the Space.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 8: 6권 전체 만들기와 찾기 적중률 확인

**Files:**
- Modify: `tests/conftest.py` (`full_corpus_dir` 추가)
- Create (복사): `tests/fixtures/search_queries.jsonl`
- Test: `tests/test_recall.py`

**Interfaces:**
- Consumes: `prep.build.build`, `assistant.corpus.Corpus`, `assistant.textnorm.match_key`
- Produces: 시험용 `full_corpus_dir` fixture (세션마다 한 번 6권 코퍼스를 임시 폴더에 만듦), 실제 `corpus/` 폴더 (git 제외)

- [ ] **Step 1: 검증 문항을 복사하고 fixture를 더한다**

```bash
mkdir -p tests/fixtures
cp docs/research/2026-09-14-groundwork/fixtures/search_verify_queries.jsonl tests/fixtures/search_queries.jsonl
wc -l tests/fixtures/search_queries.jsonl
```
Expected: `42 tests/fixtures/search_queries.jsonl`

`tests/conftest.py` 파일 끝에 덧붙인다 (import는 파일 위쪽 `from prep.volumes import VOLUMES`를 `from prep.volumes import CORPUS_YEARS, VOLUMES`로 바꾼다):
```python
@pytest.fixture(scope="session")
def full_corpus_dir(tmp_path_factory):
    from prep.build import build

    out = tmp_path_factory.mktemp("corpus")
    build(out, list(CORPUS_YEARS))
    return out
```

- [ ] **Step 2: 실패하는(아직 실행해 본 적 없는) 시험을 쓴다**

`tests/test_recall.py`:
```python
import json
from pathlib import Path

import pytest

from assistant.corpus import Corpus
from assistant.textnorm import match_key

pytestmark = [pytest.mark.pdf, pytest.mark.slow]

QUERIES = Path(__file__).with_name("fixtures") / "search_queries.jsonl"


def _is_gold(page: dict, gold: list[dict]) -> bool:
    text = match_key(page["text"])
    return any(page["year"] == g["year"] and any(all(match_key(n) in text for n in needles) for needles in g["any"])
               for g in gold)


def test_keyword_search_recall_at_10(full_corpus_dir):
    corpus = Corpus(full_corpus_dir)
    queries = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    misses = []
    for q in queries:
        hits = corpus.search(q["keywords"], years=q["years"], k=10)["hits"]
        if not any(_is_gold(corpus.pages[h["page_id"]], q["gold"]) for h in hits):
            misses.append(q["id"])
    found = len(queries) - len(misses)
    print(f"recall@10 = {found}/{len(queries)}; misses: {misses}")
    assert len(queries) == 42
    assert found / len(queries) >= 0.90, misses


def test_full_corpus_counts(full_corpus_dir):
    corpus = Corpus(full_corpus_dir)
    halves: dict[int, int] = {}
    for page in corpus.pages.values():
        halves[page["year"]] = halves.get(page["year"], 0) + 1
    assert halves == {2020: 380, 2021: 284, 2022: 346, 2023: 397, 2024: 387, 2025: 342}
    assert len(corpus.missing) == 3
    assert set(corpus.toc) == {2020, 2021, 2022, 2023, 2024, 2025}
```

- [ ] **Step 3: 시험을 돌린다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/test_recall.py -v -s`
Expected: 2 passed, 출력에 `recall@10 = 38/42` 이상 (6권 코퍼스를 만드느라 몇 분 걸린다)

실패하면 고치기 전에 원인부터 확인한다(systematic-debugging). 적중률이 90%에 못 미치면, `misses`에 나온 문항의 정답 쪽이 `citable`인지와 그 쪽의 `text`에 정답 말이 들어 있는지부터 본다.

- [ ] **Step 4: 실제 `corpus/`를 만든다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m prep.build`
Expected: 통계 JSON에 `"halves": 2136`이 나오고, `corpus/` 폴더가 생긴다.

```bash
git status --short
```
Expected: `corpus/`가 목록에 **없다** (git 제외 확인).

- [ ] **Step 5: 커밋한다**

```bash
git add tests/conftest.py tests/fixtures/search_queries.jsonl tests/test_recall.py
git commit -F - <<'EOF'
test: Check search recall on the full corpus

Build all six volumes once per test session and require recall@10 of
at least 90 percent on the 42 groundwork queries written from randomly
sampled pages, plus exact half counts per volume and the three missing
2025 image parts.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 9: 마무리 — 전체 시험, 합치기, 올리기

**Files:**
- Modify (문제가 있었을 때만): `docs/에러노트.md`

**Interfaces:**
- Consumes: 앞 Task 전부
- Produces: main에 합쳐지고 GitHub에 올라간 계획 1 결과

- [ ] **Step 1: 빠른 시험과 느린 시험을 모두 돌린다**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest -m "not slow" -q`
Expected: 모두 passed

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest -m slow -q`
Expected: 2 passed

- [ ] **Step 2: 에러노트를 확인한다**

이 계획을 하면서 고친 문제가 있었으면 `docs/에러노트.md`에 적는다. 파일이 없으면 만든다. 항목은 날짜, 증상, 원인, 해결, 배운 점이다. 고친 문제가 없었으면 이 단계는 건너뛴다.

```bash
git add docs/에러노트.md
git commit -F - <<'EOF'
docs: Record issues fixed during corpus prep

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 3: main에 합치고 올린다**

```bash
git checkout main
git merge feature/corpus-prep
git push origin main
git branch -d feature/corpus-prep
git log --oneline -12
git status --short
```
Expected: push 성공, `feature/corpus-prep` 가지 삭제, `git status --short` 비어 있음.

---

## 이 계획에서 하지 않는 것 (계획 2 이후)

- Claude API 연결, 도구 정의, 인용 블록(search_result) 만들기 → 계획 2
- 정답지 20문제와 자동 채점 → 계획 2
- 요약 · 표 뽑기 · 비교, 화면, Hugging Face 배포, 요금 안전장치 → 계획 3~4
