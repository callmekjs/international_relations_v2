import pytest

from assistant.citations import (PARAGRAPH_ONLY, UNSUPPORTED, VERIFIED, ShownPage, check_citation, cite_key, keyed,
                                 verify_answer)

P1 = ShownPage("2023-p020L", 2023, "2023년치 38쪽", (
    "한\u00b7미 정상회담이 4월 26일 워싱턴에서 열렸다.",
    "양국은 확장억제 강화를 위한 워싱턴 선언을 채택하였다.",
    "교육생 총 47명(일반 외교 44명, 지역 외교 3명)이 참여하였다.",
    "제1\u00b72차 한미 핵협의그룹 회의가 개최되었다.",
    "대북 제재 위반 사례는 전년 대비 증가하였다.",
))
P2 = ShownPage("2023-p020R", 2023, "2023년치 39쪽", ("8월 18일 캠프 데이비드에서 한미일 정상회의가 개최되었다.",))
P3 = ShownPage("2024-p020L", 2024, "2024년치 38쪽", ("신속해외송금 지원 실적은 257건이었다.",))
SHOWN = {page.page_id: page for page in (P1, P2, P3)}


def cite(page_id, paragraph, quote):
    return {"page_id": page_id, "paragraph": paragraph, "quote": quote}


def test_exact_quote_in_the_cited_paragraph_is_verified():
    c = check_citation(cite("2023-p020L", 2, "확장억제 강화를 위한 워싱턴 선언을 채택"), SHOWN)
    assert (c["grade"], c["reason"], c["corrected"]) == (VERIFIED, "exact", None)
    assert c["evidence"] == "확장억제 강화를 위한 워싱턴 선언을 채택"
    assert (c["found_page_id"], c["found_paragraph"], c["label"]) == ("2023-p020L", 2, "2023년치 38쪽")


@pytest.mark.parametrize("quote", [
    "한미 정상회담이 4월 26일 워싱턴에서",
    "한\u318d미 정상회담이 4월 26일 워싱턴에서",
    "한\u00b7미정상회담이 4월26일 워싱턴에서",
    "\u2026정상회담이 4월 26일 워싱턴에서 열렸다.",
])
def test_spacing_dot_variants_and_edges_still_verify(quote):
    assert check_citation(cite("2023-p020L", 1, quote), SHOWN)["grade"] == VERIFIED


def test_changed_meaning_is_only_paragraph_checked():
    c = check_citation(cite("2023-p020L", 5, "대북 제재 위반 사례는 전년 대비 감소하였다"), SHOWN)
    assert (c["grade"], c["reason"], c["evidence"]) == (PARAGRAPH_ONLY, "quote_not_in_paragraph", None)


def test_dots_and_dashes_between_digits_are_not_deleted():
    assert check_citation(cite("2023-p020L", 4, "제12차 한미 핵협의그룹 회의가"), SHOWN)["grade"] == PARAGRAPH_ONLY
    assert check_citation(cite("2023-p020L", 4, "제1\u00b72차 한미 핵협의그룹 회의가"), SHOWN)["grade"] == VERIFIED
    assert check_citation(cite("2023-p020L", 4, "제1-2차 한미 핵협의그룹 회의가"), SHOWN)["grade"] == VERIFIED


def test_quote_may_not_start_inside_a_longer_number():
    assert check_citation(cite("2023-p020L", 3, "7명(일반 외교 44명, 지역 외교 3명)"), SHOWN)["grade"] == PARAGRAPH_ONLY
    assert check_citation(cite("2023-p020L", 3, "47명(일반 외교 44명, 지역 외교 3명)"), SHOWN)["grade"] == VERIFIED


def test_short_quotes_prove_nothing():
    c = check_citation(cite("2023-p020L", 1, "워싱턴에서 열렸다"), SHOWN)
    assert (c["grade"], c["reason"]) == (PARAGRAPH_ONLY, "quote_too_short")
    assert check_citation(cite("2023-p999L", 1, "워싱턴에서 열렸다"), SHOWN)["grade"] == UNSUPPORTED


def test_right_page_wrong_paragraph_is_verified_and_marked():
    c = check_citation(cite("2023-p020L", 1, "확장억제 강화를 위한 워싱턴 선언을 채택"), SHOWN)
    assert (c["grade"], c["reason"], c["corrected"], c["found_paragraph"]) == (VERIFIED, "moved_paragraph", "paragraph", 2)


def test_wrong_page_is_corrected_only_within_the_same_year():
    moved = check_citation(cite("2023-p020L", 1, "캠프 데이비드에서 한미일 정상회의가 개최"), SHOWN)
    assert (moved["grade"], moved["corrected"], moved["found_page_id"], moved["found_paragraph"]) == (
        VERIFIED, "page", "2023-p020R", 1)
    invented = check_citation(cite("2023-p555L", 3, "캠프 데이비드에서 한미일 정상회의가 개최"), SHOWN)
    assert (invented["grade"], invented["corrected"]) == (VERIFIED, "page")
    other_year = check_citation(cite("2023-p020L", 1, "신속해외송금 지원 실적은 257건"), SHOWN)
    assert other_year["grade"] == PARAGRAPH_ONLY
    unread = check_citation(cite("2023-p999L", 1, "신속해외송금 지원 실적은 257건"), SHOWN)
    assert (unread["grade"], unread["reason"]) == (UNSUPPORTED, "page_not_read")


def test_paragraph_number_must_exist():
    c = check_citation(cite("2024-p020L", 7, "이 문장은 어느 쪽에도 없는 구절이다"), SHOWN)
    assert (c["grade"], c["reason"]) == (UNSUPPORTED, "no_such_paragraph")


def test_answer_gets_badges_and_shared_reference_numbers():
    answer = {"status": "answered", "sentences": [
        {"text": "정상회담은 워싱턴에서 열렸습니다.", "citations": [cite("2023-p020L", 1, "4월 26일 워싱턴에서 열렸다"),
                                                cite("2023-p020L", 1, "4월 26일 워싱턴에서 열렸다")]},
        {"text": "정상들은 선언을 냈습니다.", "citations": [cite("2023-p020L", 2, "워싱턴 선언을 발표하였다 확장억제"),
                                               cite("2023-p999L", 1, "이 구절은 어디에도 없는 문장이다")]},
        {"text": "같은 회담입니다.", "citations": [cite("2023-p020L", 1, "4월 26일 워싱턴에서 열렸다")]},
        {"text": "자세한 내용은 아래와 같습니다.", "citations": []},
    ]}
    out = verify_answer(answer, SHOWN)
    assert out["status"] == "answered"
    assert [s["badge"] for s in out["sentences"]] == ["확인됨", "문단만 확인", "확인됨", "근거 없음"]
    assert [s["refs"] for s in out["sentences"]] == [[1], [2], [1], []]
    assert len(out["sentences"][0]["citations"]) == 1
    assert out["references"][0]["quote"] == "4월 26일 워싱턴에서 열렸다"
    assert (out["references"][1]["grade"], out["references"][1]["quote"]) == (PARAGRAPH_ONLY, "워싱턴 선언을 발표하였다 확장억제")
    assert out["counts"] == {"verified": 2, "paragraph_only": 1, "unsupported": 1}


@pytest.mark.parametrize("text", ["한\u00b7미 정상회담 (4.26)", "제1\u20132차 회의 \u2192 합의",
                                  "KNDA-CEIP-JIIA 3자 회의", "\uff08-3.5%\uff09 감소"])
def test_keyed_matches_cite_key(text):
    display, key, positions = keyed(text)
    assert key == cite_key(text)
    assert len(positions) == len(key)


def test_cite_key_ignores_hyphens_between_words():
    assert cite_key("KNDA-CEIP-JIIA") == cite_key("KNDA CEIP JIIA") == "kndaceipjiia"
