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
