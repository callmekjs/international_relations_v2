"""외교백서 AI 조수 — OpenAI(gpt-5.6-sol, Responses API) 오류·미완료 상태 처리 스케치.

- 계획 2용 초안. API에 대고 실행한 적 없음 (py_compile + 가짜 객체 자체 점검만).
- 근거 문서는 같은 폴더 limits_errors.md 의 표 번호(E1, R3 ...)로 표시.
- openai 패키지 없이도 import 되도록 SDK 예외는 클래스 이름·속성(duck typing)으로 판별한다.
  (openai 3.14.0 소스 확인: APIStatusError.status_code / .code / .type / .request_id,
   APIConnectionError, APITimeoutError(APIConnectionError 하위), 스트림 중 오류는 APIError)

화면 흐름에서 쓰는 곳
1) 요청을 보내기 전: client.moderations.create(model="omni-moderation-latest", input=질문).results[0] → notice_for_moderation()
2) 요청이 예외로 끝남(스트림 시작 전 HTTP 오류, 연결/시간 초과, 스트림 중 오류): notice_for_exception()
3) 스트림 이벤트를 받는 중: notice_for_stream_event()  (response.failed / response.incomplete / error / refusal)
4) 응답 객체를 다 받은 뒤: notice_for_response()
5) 앱이 스스로 거는 한도(도구 10번, 토큰 상한, 방문자·하루 한도): APP_NOTICES
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Mapping, Optional

# ---------------------------------------------------------------------------
# 1. 결과 형식
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserNotice:
    kind: str                 # 기록·화면 분기용 고정 키
    message_ko: str           # 방문자에게 보여줄 문장
    app_retry: bool = False   # 앱이 (스트림 시작 전에 한해) 다시 보내도 되나
    alert_owner: bool = False # 운영자(주석님)에게 알려야 하나
    show_examples: bool = False  # "예시 모음" 탭으로 안내할까
    status_for_record: str = "error"  # 실행 기록의 상태: error / refused / partial / answered
    doc_ref: str = ""         # limits_errors.md 표 번호


GO_EXAMPLES = " 미리 돌려 둔 '예시 모음'은 계속 볼 수 있어요."

# ---------------------------------------------------------------------------
# 2. HTTP 오류 (스트림 시작 전) — status + error.code / error.type
# ---------------------------------------------------------------------------

# 요금·한도 계열: 다시 보내도 풀리지 않는다 (E3 "Retrying billing, spend, or quota errors won't restore API access")
BILLING_CODES: dict[str, UserNotice] = {
    "project_spend_limit_exceeded": UserNotice(
        "budget_project", "이번 달 사용량이 다 찼어요." + GO_EXAMPLES,
        alert_owner=True, show_examples=True, doc_ref="S2,E2"),
    "organization_spend_limit_exceeded": UserNotice(
        "budget_org", "이번 달 사용량이 다 찼어요." + GO_EXAMPLES,
        alert_owner=True, show_examples=True, doc_ref="S2,E2"),
    "organization_usage_limit_exceeded": UserNotice(
        "usage_limit_openai", "이번 달 사용량이 다 찼어요." + GO_EXAMPLES,
        alert_owner=True, show_examples=True, doc_ref="S4,E2"),
    "credit_balance_exhausted": UserNotice(
        "credit_exhausted", "이번 달 사용량이 다 찼어요." + GO_EXAMPLES,
        alert_owner=True, show_examples=True, doc_ref="E2"),
}

BILLING_FALLBACK = UserNotice(
    "billing_other", "이번 달 사용량이 다 찼어요." + GO_EXAMPLES,
    alert_owner=True, show_examples=True, doc_ref="E3")
BUSY = UserNotice(
    "busy", "지금 요청이 몰려 있어요. 잠시 뒤 다시 해 주세요.",
    app_retry=True, doc_ref="E2,L4")
OVERLOADED = UserNotice(
    "overloaded", "AI 서버가 붐벼요. 잠시 뒤 다시 해 주세요.",
    app_retry=True, doc_ref="E2,L4")
SERVER_ERROR = UserNotice(
    "server_error", "AI 서버에 잠시 문제가 생겼어요. 잠시 뒤 다시 해 주세요.",
    app_retry=True, doc_ref="E2")
CONFIG_ERROR = UserNotice(
    "config_error", "서비스 설정에 문제가 있어요. 운영자에게 알렸어요." + GO_EXAMPLES,
    alert_owner=True, show_examples=True, doc_ref="E2,K6")
REGION_ERROR = UserNotice(
    "region_not_supported", "지금 서버 위치에서는 AI를 쓸 수 없어요. 운영자에게 알렸어요." + GO_EXAMPLES,
    alert_owner=True, show_examples=True, doc_ref="E2,T4")
BAD_REQUEST = UserNotice(
    "bad_request", "요청을 처리하지 못했어요. 운영자에게 알렸어요.",
    alert_owner=True, doc_ref="E2")
SAFETY_STOP = UserNotice(
    "safety_stop", "안전 점검에 걸려 이 질문은 처리할 수 없어요. 외교백서 내용을 물어봐 주세요.",
    status_for_record="refused", doc_ref="R8,R9,R10")
IDENTIFIER_BLOCKED = UserNotice(
    "identifier_blocked", "이 브라우저에서는 더 이상 질문할 수 없어요." + GO_EXAMPLES,
    alert_owner=True, show_examples=True, status_for_record="refused", doc_ref="R7")
TIMEOUT = UserNotice(
    "timeout", "답이 너무 오래 걸려 멈췄어요. 다시 해 주세요.",
    app_retry=True, doc_ref="P5,E2")
CONNECTION = UserNotice(
    "connection", "AI 서버에 연결하지 못했어요. 잠시 뒤 다시 해 주세요.",
    app_retry=True, doc_ref="E2")
STREAM_BROKEN = UserNotice(
    # 스트림 도중 오류: 이미 화면에 일부가 나갔을 수 있으므로 자동 재전송 금지 (L5, P6)
    "stream_broken", "답을 만드는 중에 연결이 끊겼어요. 다시 해 주세요.",
    app_retry=False, status_for_record="partial", doc_ref="L5,P6")
UNKNOWN = UserNotice(
    "unknown", "알 수 없는 문제가 생겼어요. 잠시 뒤 다시 해 주세요.",
    alert_owner=True, doc_ref="-")

SAFETY_CODES = {"misalignment_policy_violation", "cyber_policy", "bio_policy"}


def _err_fields(exc: Any) -> tuple[Optional[int], Optional[str], Optional[str], str]:
    status = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    etype = getattr(exc, "type", None)
    msg = str(getattr(exc, "message", "") or exc)
    return status, code, etype, msg


def notice_for_exception(exc: BaseException, *, output_already_shown: bool = False) -> UserNotice:
    """SDK 예외 → 방문자 안내. output_already_shown=True 이면 재전송 금지."""
    name = type(exc).__name__
    mro_names = {c.__name__ for c in type(exc).__mro__}
    status, code, etype, msg = _err_fields(exc)

    # 연결 계열 (APITimeoutError 는 APIConnectionError 의 하위 클래스라 먼저 본다)
    if "APITimeoutError" in mro_names:
        return STREAM_BROKEN if output_already_shown else TIMEOUT
    if "APIConnectionError" in mro_names:
        return STREAM_BROKEN if output_already_shown else CONNECTION

    # 스트림 도중 오류: SDK 는 status 없는 APIError 를 던진다 (openai/_streaming.py)
    if status is None:
        if code in SAFETY_CODES:
            return SAFETY_STOP
        if output_already_shown or name == "APIError":
            return STREAM_BROKEN
        return UNKNOWN

    # 요금·한도: code 로 판별, type 이 insufficient_quota 여도 같은 묶음 (E3)
    if code in BILLING_CODES:
        return BILLING_CODES[code]
    if etype == "insufficient_quota":
        return BILLING_FALLBACK

    if code in SAFETY_CODES:
        return SAFETY_STOP
    if "identifier" in msg.lower() and "blocked" in msg.lower():
        # 문서에는 "`identifier blocked` error" 라고만 있고 status/code 형식은 미확인 (R7)
        return IDENTIFIER_BLOCKED

    if status == 429:          # slow_down, rate_limit_exceeded, 기타 요청·토큰 속도 한도
        return BUSY
    if status == 503:          # server_is_overloaded
        return OVERLOADED
    if status >= 500:
        return SERVER_ERROR
    if status == 401:          # 잘못된 키, 폐기된 키, ip_not_authorized
        return CONFIG_ERROR
    if status == 403:          # 지원 안 되는 국가, 권한 없음 (misalignment 는 위에서 처리)
        return REGION_ERROR if "country" in msg.lower() or "region" in msg.lower() else CONFIG_ERROR
    if status == 400 and getattr(exc, "param", None) == "service_tier":
        return CONFIG_ERROR
    if status in (400, 404, 409, 422):
        return BAD_REQUEST
    return UNKNOWN



# ---------------------------------------------------------------------------
# 3. 응답 객체 상태 (status / incomplete_details / error / refusal)
# ---------------------------------------------------------------------------

REFUSED = UserNotice(
    "model_refusal", "답할 수 없는 질문이에요. 외교백서 내용을 물어봐 주세요.",
    status_for_record="refused", doc_ref="R1,R2")
CUT_BY_TOKENS_WITH_TEXT = UserNotice(
    "incomplete_max_output_tokens_partial", "답이 길어 중간에 끊겼어요. 아래는 끊기기 전까지의 답이에요.",
    status_for_record="partial", doc_ref="R3")
CUT_BY_TOKENS_NO_TEXT = UserNotice(
    # 추론(reasoning)에 한도를 다 써서 보이는 답이 없는 경우. 요금은 이미 나감 (R3)
    "incomplete_max_output_tokens_empty", "생각하는 데 한도를 다 써서 답을 만들지 못했어요. 질문을 짧게 나눠 다시 해 주세요.",
    status_for_record="error", doc_ref="R3")
CUT_BY_FILTER = UserNotice(
    "incomplete_content_filter", "안전 기준에 걸려 답이 중간에 멈췄어요.",
    status_for_record="refused", doc_ref="R4")
CANCELLED = UserNotice("cancelled", "요청이 취소됐어요.", doc_ref="R5")


def _output_text(resp: Any) -> str:
    text = getattr(resp, "output_text", None)
    if isinstance(text, str):
        return text
    parts: list[str] = []
    for item in getattr(resp, "output", None) or []:
        if getattr(item, "type", None) == "message":
            for c in getattr(item, "content", None) or []:
                if getattr(c, "type", None) == "output_text":
                    parts.append(getattr(c, "text", ""))
    return "".join(parts)


def find_refusal(resp: Any) -> Optional[str]:
    """output[].type == "message" 안의 content[].type == "refusal" 을 찾는다 (R1)."""
    for item in getattr(resp, "output", None) or []:
        if getattr(item, "type", None) != "message":
            continue
        for c in getattr(item, "content", None) or []:
            if getattr(c, "type", None) == "refusal":
                return getattr(c, "refusal", "") or ""
    return None


def notice_for_response(resp: Any) -> Optional[UserNotice]:
    """None 이면 정상(completed, 거절 없음). 그 밖에는 안내를 돌려준다."""
    status = getattr(resp, "status", None)

    if status == "failed":
        err = getattr(resp, "error", None)
        code = getattr(err, "code", None)
        if code in SAFETY_CODES:
            return SAFETY_STOP
        if code == "rate_limit_exceeded":
            return BUSY
        if code == "server_error":
            return SERVER_ERROR
        return UNKNOWN  # invalid_prompt, 이미지 관련 코드 등 (이 앱에서는 예상 밖)

    if status == "incomplete":
        details = getattr(resp, "incomplete_details", None)
        reason = getattr(details, "reason", None)
        if reason == "max_output_tokens":
            return CUT_BY_TOKENS_WITH_TEXT if _output_text(resp).strip() else CUT_BY_TOKENS_NO_TEXT
        if reason == "content_filter":
            return CUT_BY_FILTER
        return UNKNOWN  # max_messages / steered 는 WebSocket 쪽 (이 앱은 안 씀)

    if status == "cancelled":
        return CANCELLED

    if status == "completed":
        if find_refusal(resp) is not None:
            return REFUSED
        return None

    return UNKNOWN  # queued / in_progress 가 최종으로 오면 이상함


# ---------------------------------------------------------------------------
# 4. 스트림 이벤트 (client.responses.create(..., stream=True) 를 직접 순회할 때)
#    주의: SDK 의 responses.stream(...).get_final_response() 는 response.completed 가
#    안 오면 RuntimeError("Didn't receive a `response.completed` event.") 를 낸다
#    (openai 3.14.0 lib/streaming/responses/_responses.py). 그래서 이벤트를 직접 본다.
# ---------------------------------------------------------------------------


def notice_for_stream_event(event: Any) -> Optional[UserNotice]:
    etype = getattr(event, "type", None)
    if etype in ("response.failed", "response.incomplete", "response.completed"):
        return notice_for_response(getattr(event, "response", None))
    if etype == "response.refusal.done":
        return REFUSED
    if etype == "error":
        code = getattr(event, "code", None)
        if code in SAFETY_CODES:
            return SAFETY_STOP
        if code in BILLING_CODES:
            return BILLING_CODES[code]
        return STREAM_BROKEN
    return None


# ---------------------------------------------------------------------------
# 5. 입력 점검(무료 moderation 엔드포인트) 결과
# ---------------------------------------------------------------------------

MODERATION_FLAGGED = UserNotice(
    "moderation_flagged", "이 질문은 받을 수 없어요. 외교백서에 관한 질문을 해 주세요.",
    status_for_record="refused", doc_ref="R6")


def notice_for_moderation(result: Any, *, block_categories: frozenset[str] = frozenset(
        {"sexual/minors", "self-harm/intent", "self-harm/instructions", "illicit/violent",
         "hate/threatening", "harassment/threatening"})) -> Optional[UserNotice]:
    """방문자 질문만 점검한다. 백서 본문(전쟁·핵·테러 서술)은 violence 로 잡힐 수 있어 넣지 않는다.
    문서: 점수는 '신호'로 쓰고 자동 차단 결정으로 쓰지 말라 (R6). 그래서 flagged 전체가 아니라
    고른 범주만 막는다 — 이 범주 목록은 추정값이며 시험으로 조정한다."""
    if result is None or getattr(result, "type", None) == "error":
        return None  # 점검 실패는 막지 않고 기록만
    cats: Mapping[str, bool] = getattr(result, "categories", None) or {}
    if hasattr(cats, "model_dump"):
        cats = cats.model_dump(by_alias=True)  # SDK 객체일 때 "sexual/minors" 같은 원래 키로
    if any(bool(cats.get(k)) for k in block_categories):
        return MODERATION_FLAGGED
    return None


# ---------------------------------------------------------------------------
# 6. 앱이 스스로 거는 한도 (설계서 4.4, 6.3) — API 문서 항목 아님
# ---------------------------------------------------------------------------

APP_NOTICES: dict[str, UserNotice] = {
    "tool_or_token_cap": UserNotice(
        "tool_or_token_cap", "충분히 찾지 못했어요. 찾은 만큼만 답했어요.", status_for_record="partial"),
    "visitor_daily_cap": UserNotice(
        "visitor_daily_cap", "오늘 질문 횟수를 다 썼어요. 한국 시간 0시에 다시 쓸 수 있어요." + GO_EXAMPLES,
        show_examples=True, status_for_record="error"),
    "global_daily_cap": UserNotice(
        "global_daily_cap", "오늘 전체 사용량이 다 찼어요. 한국 시간 0시에 다시 열려요." + GO_EXAMPLES,
        show_examples=True, status_for_record="error"),
}


# ---------------------------------------------------------------------------
# 7. 재시도 · 안전 식별자 · 클라이언트 설정
# ---------------------------------------------------------------------------

MAX_APP_RETRIES = 2
MAX_RETRY_AFTER_S = 20.0  # 웹 화면에서 기다려 줄 최대 시간(추정값). 넘으면 재시도하지 않고 안내.


def retry_delay_s(exc: BaseException, attempt: int) -> Optional[float]:
    """다시 보낼지와 대기 시간. None 이면 재시도하지 않는다.
    - 스트림이 시작돼 출력을 받은 뒤에는 호출하지 말 것 (L5, P6)
    - 요금·한도·설정·안전 오류는 재시도 안 함 (E3, L6)
    - Retry-After 가 있으면 그 이상 기다림 (L3, L6)
    - 없으면 지수 백오프 + 무작위 지연 (L6)"""
    if attempt >= MAX_APP_RETRIES:
        return None
    if not notice_for_exception(exc).app_retry:
        return None
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    ra = None
    for name, div in (("retry-after-ms", 1000.0), ("retry-after", 1.0)):
        raw = headers.get(name) if hasattr(headers, "get") else None
        if raw is not None:
            try:
                ra = float(raw) / div
                break
            except ValueError:
                pass
    if ra is not None:
        if ra > MAX_RETRY_AFTER_S:
            return None  # 서버가 오래 기다리라고 함 → 지금은 안내만
        return ra + random.uniform(0.1, 0.5)
    return min(0.5 * (2 ** attempt), 8.0) * random.uniform(0.75, 1.0)


def safety_identifier_for(visitor_hash_source: str, salt: str) -> str:
    """방문자 해시(설계서 6.3: IP + 브라우저 정보) → safety_identifier.
    문서: 최대 64자, 이름·이메일은 해시해서 보낼 것, 로그인 없는 미리보기는 세션 ID 도 가능 (R7).
    sha256 hex 는 정확히 64자. salt 는 Space Secrets 에 둔다."""
    return hashlib.sha256((salt + "|" + visitor_hash_source).encode("utf-8")).hexdigest()


# 권장 요청 인자 (계획 2에서 확정). 값은 추정 시작점.
RECOMMENDED_REQUEST_KWARGS: dict[str, Any] = {
    "model": "gpt-5.6-sol",
    "store": False,                 # 기본값 true → 30일 저장 + 대시보드 로그. 공개 데모는 끔 (D2, D3)
    "max_output_tokens": 25000,     # 추론+답 합계 상한. 문서 권장 시작 여유 25,000 (R3)
    "stream": True,
    # "safety_identifier": safety_identifier_for(...),   # 요청마다 (R7)
    # store=False 이므로 도구 호출 루프에서는 이전 응답의 output 항목(암호화된 reasoning 포함)을
    # 그대로 다음 input 에 이어 붙인다 (D4). previous_response_id 는 쓰지 않는다.
}

# 권장 클라이언트 설정: SDK 자동 재시도는 끄고(max_retries=0) 위 retry_delay_s 로 직접 제한.
# 이유: SDK 3.14.0 은 x-should-retry 헤더가 없으면 429 를 모두(요금 한도 429 포함) 재시도함 (P3).
RECOMMENDED_CLIENT_KWARGS: dict[str, Any] = {
    "max_retries": 0,
    "timeout": 180.0,  # SDK 기본 600초(연결 5초). 웹 화면용으로 줄임 — 추정값
}


# ---------------------------------------------------------------------------
# 8. 가짜 객체 자체 점검 (API 호출 없음)
# ---------------------------------------------------------------------------


def _selftest() -> None:
    from types import SimpleNamespace as NS

    class APIError(Exception):
        def __init__(self, message: str, code: Optional[str] = None) -> None:
            super().__init__(message)
            self.message, self.code, self.type, self.param = message, code, None, None

    class APIStatusError(APIError):
        def __init__(self, status: int, code: Optional[str], etype: Optional[str], message: str = "",
                     headers: Optional[dict] = None, param: Optional[str] = None) -> None:
            super().__init__(message, code)
            self.status_code, self.type, self.param = status, etype, param
            self.response = NS(headers=headers or {})

    class RateLimitError(APIStatusError): ...
    class InternalServerError(APIStatusError): ...
    class PermissionDeniedError(APIStatusError): ...
    class APIConnectionError(APIError): ...
    class APITimeoutError(APIConnectionError): ...

    assert notice_for_exception(RateLimitError(429, "project_spend_limit_exceeded", "insufficient_quota")).kind == "budget_project"
    assert notice_for_exception(RateLimitError(429, "brand_new_billing_code", "insufficient_quota")).kind == "billing_other"
    assert notice_for_exception(RateLimitError(429, "slow_down", "rate_limit_error")).kind == "busy"
    assert notice_for_exception(InternalServerError(503, "server_is_overloaded", "service_unavailable_error")).kind == "overloaded"
    assert notice_for_exception(PermissionDeniedError(403, "misalignment_policy_violation", "invalid_request_error")).kind == "safety_stop"
    assert notice_for_exception(APITimeoutError("Request timed out.")).kind == "timeout"
    assert notice_for_exception(APIConnectionError("x"), output_already_shown=True).kind == "stream_broken"
    assert notice_for_exception(APIError("An error occurred during streaming")).kind == "stream_broken"
    assert retry_delay_s(RateLimitError(429, "project_spend_limit_exceeded", "insufficient_quota"), 0) is None
    assert retry_delay_s(RateLimitError(429, "slow_down", "rate_limit_error", headers={"retry-after": "3"}), 0) >= 3
    assert retry_delay_s(RateLimitError(429, "slow_down", "rate_limit_error", headers={"retry-after": "56"}), 0) is None
    assert retry_delay_s(RateLimitError(429, "slow_down", "rate_limit_error"), 2) is None

    msg = lambda *c: NS(type="message", content=list(c))  # noqa: E731
    ok = NS(status="completed", output=[msg(NS(type="output_text", text="답"))], output_text="답")
    refused = NS(status="completed", output=[msg(NS(type="refusal", refusal="I'm sorry"))], output_text="")
    cut_empty = NS(status="incomplete", incomplete_details=NS(reason="max_output_tokens"),
                   output=[NS(type="reasoning")], output_text="")
    cut_text = NS(status="incomplete", incomplete_details=NS(reason="max_output_tokens"),
                  output=[msg(NS(type="output_text", text="부분"))], output_text="부분")
    filt = NS(status="incomplete", incomplete_details=NS(reason="content_filter"), output=[], output_text="")
    failed = NS(status="failed", error=NS(code="bio_policy"), output=[])
    assert notice_for_response(ok) is None
    assert notice_for_response(refused).kind == "model_refusal"
    assert notice_for_response(cut_empty).kind == "incomplete_max_output_tokens_empty"
    assert notice_for_response(cut_text).kind == "incomplete_max_output_tokens_partial"
    assert notice_for_response(filt).kind == "incomplete_content_filter"
    assert notice_for_response(failed).kind == "safety_stop"
    assert notice_for_stream_event(NS(type="response.incomplete", response=filt)).kind == "incomplete_content_filter"
    assert notice_for_stream_event(NS(type="error", code="cyber_policy", message="x")).kind == "safety_stop"
    assert notice_for_stream_event(NS(type="response.output_text.delta", delta="a")) is None
    assert notice_for_moderation(NS(type="moderation_result", flagged=True, categories={"violence": True})) is None
    assert notice_for_moderation(NS(type="moderation_result", flagged=True, categories={"sexual/minors": True})).kind == "moderation_flagged"
    assert len(safety_identifier_for("1.2.3.4|UA", "salt")) == 64
    print("selftest ok")


if __name__ == "__main__":
    _selftest()
