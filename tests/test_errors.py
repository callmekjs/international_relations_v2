from types import SimpleNamespace as NS

import pytest

from assistant.errors import (ANSWER_CUT, BILLING, CONTENT_FILTER, REFUSED, SAFETY_STOP, SERVER_ERROR, UNKNOWN,
                              UserNotice, notice_for_exception, notice_for_moderation, notice_for_stream_error,
                              notice_for_turn, retry_delay_s, stream_retry_delay_s)
from assistant.llm import TurnResult


# Stand-ins named like the openai 3.14.0 exception classes (errors.py matches by class name).
class APIError(Exception):
    def __init__(self, message="", code=None, etype=None):
        super().__init__(message)
        self.message, self.code, self.type = message, code, etype


class APIStatusError(APIError):
    def __init__(self, status, code=None, etype=None, headers=None):
        super().__init__("status error", code, etype)
        self.status_code = status
        self.response = NS(headers=headers or {})


class RateLimitError(APIStatusError):
    pass


class APIConnectionError(APIError):
    pass


class APITimeoutError(APIConnectionError):
    pass


@pytest.mark.parametrize("exc, kind", [
    (RateLimitError(429, "project_spend_limit_exceeded", "insufficient_quota"), "budget"),
    (RateLimitError(429, "some_new_billing_code", "insufficient_quota"), "budget"),
    (RateLimitError(429, "rate_limit_exceeded", "requests"), "busy"),
    (APIStatusError(503, "server_is_overloaded"), "server_error"),
    (APIStatusError(401, "invalid_api_key"), "config_error"),
    (APIStatusError(400, "invalid_value"), "bad_request"),
    (APIStatusError(403, "cyber_policy"), "safety_stop"),
    (APITimeoutError("timed out"), "timeout"),
    (APIConnectionError("no route"), "connection"),
    (APIError("An error occurred during streaming"), "stream_broken"),
    (APIStatusError(408, "request_timeout"), "timeout"),
    (APIStatusError(409, "conflict"), "server_error"),
    (APIError("limit", code="insufficient_quota"), "budget"),
    (APIError("policy", code="cyber_policy"), "safety_stop"),
])
def test_exceptions_map_to_notices(exc, kind):
    assert notice_for_exception(exc).kind == kind


def test_after_output_was_shown_errors_are_a_broken_stream():
    assert notice_for_exception(APIConnectionError("x"), output_already_shown=True).kind == "stream_broken"
    assert notice_for_exception(RateLimitError(429, "rate_limit_exceeded"), output_already_shown=True).kind == "stream_broken"
    assert notice_for_exception(RateLimitError(429, "project_spend_limit_exceeded"), output_already_shown=True).kind == "budget"


def test_retry_rules():
    assert retry_delay_s(RateLimitError(429, "project_spend_limit_exceeded", "insufficient_quota"), 0) is None
    assert 0 < retry_delay_s(RateLimitError(429, "rate_limit_exceeded"), 0) <= 0.5
    assert retry_delay_s(RateLimitError(429, "rate_limit_exceeded", headers={"retry-after": "3"}), 0) >= 3.1
    assert retry_delay_s(RateLimitError(429, "rate_limit_exceeded", headers={"retry-after": "56"}), 0) is None
    assert retry_delay_s(APIStatusError(500), 2) is None
    assert 0 < retry_delay_s(APIStatusError(500), 1) <= 1.0
    assert 0 < stream_retry_delay_s("server_error", 0) <= 0.5
    assert 0 < stream_retry_delay_s(None, 1) <= 1.0
    assert stream_retry_delay_s("server_error", 2) is None
    assert stream_retry_delay_s("cyber_policy", 0) is None
    assert stream_retry_delay_s("project_spend_limit_exceeded", 0) is None


def turn(status="completed", **fields):
    return TurnResult(status, [], [], fields.pop("answer_text", ""), **fields)


def test_turn_results_map_to_notices():
    assert notice_for_turn(turn()) is None
    assert notice_for_turn(turn(refusal="I can't help")) is REFUSED
    assert notice_for_turn(turn("incomplete", incomplete_reason="max_output_tokens")) is ANSWER_CUT
    assert notice_for_turn(turn("incomplete", incomplete_reason="content_filter")) is CONTENT_FILTER
    assert notice_for_turn(turn("failed", error_code="bio_policy")) is SAFETY_STOP
    assert notice_for_turn(turn("failed", error_code="server_error")) is SERVER_ERROR
    assert notice_for_turn(turn("failed", error_code="invalid_prompt")) is UNKNOWN


def test_stream_error_codes_and_moderation():
    assert notice_for_stream_error("cyber_policy").kind == "safety_stop"
    assert notice_for_stream_error("project_spend_limit_exceeded").kind == "budget"
    assert notice_for_stream_error(None).kind == "stream_broken"
    assert notice_for_moderation(["violence"]) is None
    assert notice_for_moderation(["sexual/minors", "violence"]).kind == "moderation_flagged"
    assert notice_for_moderation([]) is None


def test_notice_to_dict_has_only_what_the_screen_needs():
    assert UserNotice("x", "안내", status="partial").to_dict() == {"kind": "x", "message": "안내"}


def test_status_less_sdk_errors_retry_like_stream_errors():
    assert 0 < retry_delay_s(APIError("An error occurred during streaming"), 0) <= 0.5
    assert 0 < retry_delay_s(APIError("boom", code="server_error"), 1) <= 1.0
    assert retry_delay_s(APIError("boom", code="server_error"), 2) is None
    assert retry_delay_s(APIError("limit", code="insufficient_quota"), 0) is None
    assert retry_delay_s(APIError("limit", etype="insufficient_quota"), 0) is None
    assert retry_delay_s(APIError("policy", code="bio_policy"), 0) is None
    assert retry_delay_s(ValueError("not an SDK error"), 0) is None


def test_odd_retry_after_values_fall_back_to_backoff():
    for raw in ("-3", "nan", "inf", "-inf"):
        assert 0 < retry_delay_s(RateLimitError(429, "rate_limit_exceeded", headers={"retry-after": raw}), 0) <= 0.5
    assert 0 < retry_delay_s(RateLimitError(429, "rate_limit_exceeded", headers={"retry-after-ms": "nan"}), 0) <= 0.5
    assert 0 < retry_delay_s(APIStatusError(408), 0) <= 0.5
    assert 0 < retry_delay_s(APIStatusError(409), 0) <= 0.5


def test_billing_codes_mean_the_budget_notice_on_every_path():
    assert notice_for_turn(turn("failed", error_code="insufficient_quota")) is BILLING
    assert notice_for_turn(turn("failed", error_code="project_spend_limit_exceeded")) is BILLING
    assert notice_for_stream_error("insufficient_quota") is BILLING
    assert stream_retry_delay_s("insufficient_quota", 0) is None
