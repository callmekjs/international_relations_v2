"""The three corpus tools the model may call (spec 4.1), defined as strict function tools.

ToolRunner turns one function call into: the text sent back to the model (compact JSON with
ensure_ascii=False; the default escaping costs about 2.9 times the tokens, groundwork O9), a
one-line Korean summary for the progress view, and a log of the pages the model was shown,
which the citation check needs. Loose inputs are coerced and bad inputs come back as an error
output instead of an exception (Plan 1 carry-over 2).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from assistant.citations import ShownPage
from assistant.corpus import MAX_READ_PAGES, Corpus
from assistant.textnorm import utf8_safe

MAX_K = 10
FRONT_MATTER_SLACK = 6  # extra hits fetched so greeting and contents pages can move to the end
TOOL_NAMES = {"search": "찾기", "read_pages": "쪽 읽기", "get_toc": "목차 보기"}
HIT_FIELDS = ("page_id", "label", "year", "chapter", "section", "is_appendix", "front_matter", "snippet")
_PAGE_ID = re.compile(r"^([0-9]{4})-p[0-9]{3}[LR]$")

TOOLS: list[dict] = [
    {
        "type": "function",
        "name": "search",
        "strict": True,
        "description": ("외교백서 본문을 인쇄 1쪽 단위로 찾는다. 결과는 page_id, 쪽 표시(label), 연도, 장과 절, "
                        "부록 여부, 인사말이나 목차인지(front_matter), 찾은 말 주변 글자(snippet)다. "
                        "order가 score면 관련 높은 순서, year_turns면 해마다 돌아가며 섞은 순서다. "
                        "snippet은 근거가 아니다. 근거로 쓰려면 read_pages로 읽는다."),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["query", "years", "k"],
            "properties": {
                "query": {"type": "string", "description": "찾을 말. 백서에 쓰였을 법한 짧은 표현. 예: 한미 정상회담"},
                "years": {"type": ["array", "null"], "items": {"type": "integer"},
                          "description": "찾을 연도(다룬 해) 목록. 모든 해를 찾으려면 null."},
                "k": {"type": ["integer", "null"], "description": "돌려받을 쪽 수 1~10. 기본값 10이면 null."},
            },
        },
    },
    {
        "type": "function",
        "name": "read_pages",
        "strict": True,
        "description": ("page_id로 쪽 원문을 읽는다. 한 번에 최대 5쪽. 쪽마다 쪽 표시와 번호 붙은 문단(paragraphs)이 온다. "
                        "근거는 여기서 읽은 쪽과 문단만 쓸 수 있다. already_read는 이미 읽어서 다시 보내지 않은 쪽이다."),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["page_ids"],
            "properties": {
                "page_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5,
                             "description": '읽을 page_id 목록. 예: ["2023-p020L", "2023-p020R"]'},
            },
        },
    },
    {
        "type": "function",
        "name": "get_toc",
        "strict": True,
        "description": "그 해 외교백서의 장과 절 제목, 시작 쪽, 자료에 없는 부분 목록을 돌려준다.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["year"],
            "properties": {"year": {"type": "integer", "description": "다룬 해. 예: 2023"}},
        },
    },
]


class ToolInputError(ValueError):
    """The model sent arguments the tool cannot use; the message goes back to the model."""


@dataclass(frozen=True)
class ToolOutcome:
    output: str   # function_call_output text for the model
    summary: str  # one line for the progress view
    ok: bool


class ToolRunner:
    def __init__(self, corpus: Corpus, allowed_years: list[int] | None = None):
        self.corpus = corpus
        self.allowed_years = sorted(set(allowed_years)) if allowed_years else None
        self.shown: dict[str, ShownPage] = {}

    def execute(self, name: str, arguments: str) -> ToolOutcome:
        handler = {"search": self._search, "read_pages": self._read_pages, "get_toc": self._get_toc}.get(name)
        try:
            if handler is None:
                raise ToolInputError(f"알 수 없는 도구입니다: {name}")
            try:
                args = json.loads(arguments or "{}")
            except json.JSONDecodeError as exc:
                raise ToolInputError("입력이 JSON 형식이 아닙니다") from exc
            if not isinstance(args, dict):
                raise ToolInputError("입력은 JSON 객체여야 합니다")
            outcome = handler(args)
        except ToolInputError as exc:
            outcome = ToolOutcome(_dumps({"error": str(exc)}), f"{TOOL_NAMES.get(name, name)} 입력 오류", False)
        return ToolOutcome(outcome.output, utf8_safe(outcome.summary), outcome.ok)  # records are written as UTF-8

    # --- search ---------------------------------------------------------------------------------
    def _search(self, args: dict) -> ToolOutcome:
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ToolInputError("query(찾을 말)가 비어 있습니다")
        query = utf8_safe(query.strip())
        years = _years(args.get("years"))
        k = max(1, min(MAX_K, _integer(args.get("k"), "k"))) if args.get("k") is not None else MAX_K
        corpus_years = self.corpus.corpus_years
        out_of_range = [y for y in years or [] if y not in corpus_years]
        wanted = [y for y in years or [] if y in corpus_years]
        notes: list[str] = []
        if years and not wanted:
            return self._search_result(query, years, [], "score", out_of_range, notes)
        if self.allowed_years:
            asked = wanted or self.allowed_years
            wanted = [y for y in asked if y in self.allowed_years]
            if len(wanted) < len(asked):
                notes.append(f"이번 질문은 {_years_text(self.allowed_years)}로 제한되어 그 밖의 해는 찾지 않았습니다")
            if not wanted:
                return self._search_result(query, asked, [], "score", out_of_range, notes)
        result = self.corpus.search(query, wanted or None, k + FRONT_MATTER_SLACK)
        hits = sorted(result["hits"], key=lambda hit: hit["front_matter"])[:k]
        return self._search_result(query, wanted or None, hits, result["order"], out_of_range, notes)

    def _search_result(self, query, years, hits, order, out_of_range, notes) -> ToolOutcome:
        payload = {"order": order, "hits": [{key: hit[key] for key in HIT_FIELDS} for hit in hits],
                   "out_of_range_years": out_of_range, "corpus_years": self.corpus.corpus_years}
        if notes:
            payload["notes"] = notes
        where = f" ({_years_text(years)})" if years else ""
        return ToolOutcome(_dumps(payload), f'찾기 "{query}"{where} \u2192 {len(hits)}쪽', True)

    # --- read_pages -----------------------------------------------------------------------------
    def _read_pages(self, args: dict) -> ToolOutcome:
        raw = args.get("page_ids")
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list) or not raw or not all(isinstance(pid, str) for pid in raw):
            raise ToolInputError("page_ids는 page_id 목록이어야 합니다")
        page_ids = list(dict.fromkeys(pid.strip() for pid in raw))
        if len(page_ids) > MAX_READ_PAGES:
            raise ToolInputError(f"한 번에 최대 {MAX_READ_PAGES}쪽까지 읽을 수 있습니다. 나눠서 읽으세요")
        already = [pid for pid in page_ids if pid in self.shown]
        out_of_scope = [pid for pid in page_ids if pid not in self.shown and not self._in_scope(pid)]
        to_read = [pid for pid in page_ids if pid not in self.shown and self._in_scope(pid)]
        result = self.corpus.read_pages(to_read) if to_read else {"pages": [], "not_found": [], "not_citable": []}
        pages = []
        for page in result["pages"]:
            self.shown[page["page_id"]] = ShownPage(page["page_id"], page["year"], page["label"],
                                                    tuple(page["paragraphs"]))
            pages.append({"page_id": page["page_id"], "label": page["label"], "chapter": page["chapter"],
                          "section": page["section"], "is_appendix": page["is_appendix"],
                          "front_matter": page["front_matter"],
                          "paragraphs": {str(n): text for n, text in enumerate(page["paragraphs"], 1)}})
        payload: dict = {"pages": pages}
        for key, ids in (("already_read", already), ("not_found", result["not_found"]),
                         ("not_citable", result["not_citable"]), ("out_of_scope", out_of_scope)):
            if ids:
                payload[key] = ids
        if out_of_scope:
            payload["notes"] = [f"이번 질문은 {_years_text(self.allowed_years)}로 제한되어 그 밖의 해 쪽은 읽지 않았습니다"]
        return ToolOutcome(_dumps(payload), self._read_summary(pages, already), True)

    def _in_scope(self, page_id: str) -> bool:
        match = _PAGE_ID.match(page_id)
        return not (self.allowed_years and match and int(match.group(1)) not in self.allowed_years)

    def _read_summary(self, pages: list[dict], already: list[str]) -> str:
        parts = [f"{self.corpus.pages[p['page_id']]['year']}년치 {self.corpus.pages[p['page_id']]['printed_page']}쪽"
                 for p in pages]
        text = ", ".join(parts) if parts else "새로 읽은 쪽 없음"
        if already:
            text += f" (이미 읽은 {len(already)}쪽 제외)"
        return f"쪽 읽기 {text}"

    # --- get_toc --------------------------------------------------------------------------------
    def _get_toc(self, args: dict) -> ToolOutcome:
        year = _integer(args.get("year"), "year")
        if self.allowed_years and year not in self.allowed_years and year in self.corpus.corpus_years:
            payload = {"year": year, "out_of_scope": True,
                       "notes": [f"이번 질문은 {_years_text(self.allowed_years)}로 제한되어 있습니다"]}
        else:
            payload = self.corpus.get_toc(year)
        return ToolOutcome(_dumps(payload), f"목차 보기 {year}년치", True)


def _dumps(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _integer(value, what: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():  # not other scripts' digits
        return int(value.strip())
    raise ToolInputError(f"{what} 값은 정수여야 합니다: {value!r}")


def _years(value) -> list[int] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        value = [value]
    return sorted({_integer(v, "years") for v in value}) or None


def _years_text(years: list[int]) -> str:
    return ", ".join(f"{year}년치" for year in years)
