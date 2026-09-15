"""What to tell the visitor when something goes wrong (spec 7) and when the app may retry
(groundwork O12). Knows no SDK: OpenAI exceptions are recognised by class name and attributes,
so this file imports nothing from openai (see limits-errors/error_handling_sketch.py)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from assistant.llm import TurnResult


@dataclass(frozen=True)
class UserNotice:
    kind: str
    message: str
    status: str = "error"        # run status when this notice ends a run without an answer
    app_retry: bool = False      # the app may send the same request again (only before any output)
    alert_owner: bool = False
    show_examples: bool = False

    def to_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message}


class LLMError(Exception):
    """A model turn could not be completed; .notice says what to show."""

    def __init__(self, notice: UserNotice):
        super().__init__(notice.kind)
        self.notice = notice


GO_EXAMPLES = " 미리 돌려 둔 '예시 모음'은 계속 볼 수 있어요."

BILLING = UserNotice("budget", "이번 달 사용량이 다 찼어요." + GO_EXAMPLES, alert_owner=True, show_examples=True)
BUSY = UserNotice("busy", "지금 요청이 몰려 있어요. 잠시 뒤 다시 해 주세요.", app_retry=True)
SERVER_ERROR = UserNotice("server_error", "AI 서버에 잠시 문제가 생겼어요. 잠시 뒤 다시 해 주세요.", app_retry=True)
TIMEOUT = UserNotice("timeout", "답이 너무 오래 걸려 멈췄어요. 다시 해 주세요.", app_retry=True)
CONNECTION = UserNotice("connection", "AI 서버에 연결하지 못했어요. 잠시 뒤 다시 해 주세요.", app_retry=True)
STREAM_BROKEN = UserNotice("stream_broken", "답을 만드는 중에 연결이 끊겼어요. 다시 해 주세요.", status="partial")
CONFIG_ERROR = UserNotice("config_error", "서비스 설정에 문제가 있어요. 운영자에게 알렸어요." + GO_EXAMPLES,
                          alert_owner=True, show_examples=True)
BAD_REQUEST = UserNotice("bad_request", "요청을 처리하지 못했어요. 운영자에게 알렸어요.", alert_owner=True)
SAFETY_STOP = UserNotice("safety_stop", "안전 점검에 걸려 이 질문은 처리할 수 없어요. 외교백서 내용을 물어봐 주세요.",
                         status="refused")
UNKNOWN = UserNotice("unknown", "알 수 없는 문제가 생겼어요. 잠시 뒤 다시 해 주세요.", alert_owner=True)
REFUSED = UserNotice("model_refusal", "답할 수 없는 질문이에요. 외교백서 내용을 물어봐 주세요.", status="refused")
ANSWER_CUT = UserNotice("answer_cut", "답이 중간에 끊겼어요. 다시 해 주세요.", status="partial")
CONTENT_FILTER = UserNotice("content_filter", "안전 기준에 걸려 답이 중간에 멈췄어요.", status="refused")
MODERATION_FLAGGED = UserNotice("moderation_flagged", "이 질문은 받을 수 없어요. 외교백서에 관한 질문을 해 주세요.",
                                status="refused")
BAD_ANSWER = UserNotice("bad_answer", "답을 정리하지 못했어요. 다시 해 주세요.")
CAP_REACHED = UserNotice("cap_reached", "충분히 찾지 못했어요. 찾은 만큼만 답했어요.", status="partial")
CAP_STOPPED = UserNotice("cap_stopped", "충분히 찾지 못해 답을 만들지 못했어요. 질문을 좁혀 다시 해 주세요.",
                         status="partial")
EMPTY_QUESTION = UserNotice("empty_question", "질문을 입력해 주세요.")
QUESTION_TOO_LONG = UserNotice("question_too_long", "질문은 300자까지 쓸 수 있어요.")
BAD_YEARS = UserNotice("bad_years", "연도는 2023처럼 숫자로 적어 주세요.")

BILLING_CODES = frozenset({"project_spend_limit_exceeded", "organization_spend_limit_exceeded",
                           "organization_usage_limit_exceeded", "credit_balance_exhausted",
                           "insufficient_quota"})
SAFETY_CODES = frozenset({"misalignment_policy_violation", "cyber_policy", "bio_policy"})
MODERATION_BLOCK = frozenset({"sexual/minors", "self-harm/intent", "self-harm/instructions", "illicit/violent",
                              "hate/threatening", "harassment/threatening"})
MAX_APP_RETRIES = 2
MAX_RETRY_AFTER_S = 20.0
MAX_ERROR_MESSAGE_CHARS = 300


def error_text(exc: BaseException) -> str:
    """'ExceptionType: message' for run records, the message cut to 300 characters."""
    return f"{type(exc).__name__}: {str(exc)[:MAX_ERROR_MESSAGE_CHARS]}"


def notice_for_exception(exc: BaseException, *, output_already_shown: bool = False) -> UserNotice:
    names = {cls.__name__ for cls in type(exc).__mro__}
    status = getattr(exc, "status_code", None)
    code = getattr(exc, "code", None)
    if "APITimeoutError" in names:
        return STREAM_BROKEN if output_already_shown else TIMEOUT
    if "APIConnectionError" in names:
        return STREAM_BROKEN if output_already_shown else CONNECTION
    if code in BILLING_CODES or getattr(exc, "type", None) == "insufficient_quota":
        return BILLING
    if status is None:  # e.g. openai.APIError raised from an SSE error payload
        return notice_for_stream_error(code)
    if code in SAFETY_CODES:
        return SAFETY_STOP
    if output_already_shown:
        return STREAM_BROKEN
    if status == 429:
        return BUSY
    if status == 408:
        return TIMEOUT
    if status >= 500 or status == 409:
        return SERVER_ERROR
    if status in (401, 403):
        return CONFIG_ERROR
    if status in (400, 404, 422):
        return BAD_REQUEST
    return UNKNOWN


def notice_for_stream_error(code: str | None) -> UserNotice:
    if code in SAFETY_CODES:
        return SAFETY_STOP
    if code in BILLING_CODES:
        return BILLING
    return STREAM_BROKEN


def notice_for_turn(turn: TurnResult) -> UserNotice | None:
    """None when the turn completed without a refusal."""
    if turn.status == "failed":
        if turn.error_code in SAFETY_CODES:
            return SAFETY_STOP
        if turn.error_code in BILLING_CODES:
            return BILLING
        if turn.error_code == "rate_limit_exceeded":
            return BUSY
        if turn.error_code == "server_error":
            return SERVER_ERROR
        return UNKNOWN
    if turn.status == "incomplete":
        return CONTENT_FILTER if turn.incomplete_reason == "content_filter" else ANSWER_CUT
    if turn.status != "completed":
        return UNKNOWN
    return REFUSED if turn.refusal is not None else None


def notice_for_moderation(flagged: list[str]) -> UserNotice | None:
    """Only a few categories block: white-paper topics (war, nuclear arms) must stay askable."""
    return MODERATION_FLAGGED if MODERATION_BLOCK.intersection(flagged) else None


def retry_delay_s(exc: BaseException, attempt: int) -> float | None:
    """Seconds to wait before sending the same request again, or None for no retry. Call it only when
    nothing from this turn has been shown yet. Billing, safety and setup errors never retry.
    A status-less SDK error (the SDK raises one for an SSE error payload) retries like a stream error."""
    if attempt >= MAX_APP_RETRIES:
        return None
    notice = notice_for_exception(exc)
    if _is_stream_payload_error(exc):
        return stream_retry_delay_s(getattr(exc, "code", None), attempt) if notice is STREAM_BROKEN else None
    if not notice.app_retry:
        return None
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    for name, per_second in (("retry-after-ms", 1000.0), ("retry-after", 1.0)):
        raw = headers.get(name) if hasattr(headers, "get") else None
        if raw is None:
            continue
        try:
            wait = float(raw) / per_second
        except (TypeError, ValueError):
            continue
        if not math.isfinite(wait) or wait < 0:
            continue
        return None if wait > MAX_RETRY_AFTER_S else wait + random.uniform(0.1, 0.5)
    return _backoff_s(attempt)


def stream_retry_delay_s(code: str | None, attempt: int) -> float | None:
    """Like retry_delay_s for a stream that sent an `error` event (or ended early) before any output
    was shown: retried like a server error, except for billing and safety codes."""
    if attempt >= MAX_APP_RETRIES or code in BILLING_CODES or code in SAFETY_CODES:
        return None
    return _backoff_s(attempt)


def _is_stream_payload_error(exc: BaseException) -> bool:
    names = {cls.__name__ for cls in type(exc).__mro__}
    return ("APIError" in names and getattr(exc, "status_code", None) is None
            and not names & {"APITimeoutError", "APIConnectionError"})


def _backoff_s(attempt: int) -> float:
    return min(0.5 * 2 ** attempt, 8.0) * random.uniform(0.75, 1.0)
