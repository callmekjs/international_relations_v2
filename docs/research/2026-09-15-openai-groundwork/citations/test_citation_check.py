"""Tests for citation_check.py on real corpus pages (2020-2025). Offline, no LLM calls.

Run from the project root (read-only use of corpus/ and assistant/):
  PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -m pytest <this file> -v -s -p no:cacheprovider
"""
import re
from pathlib import Path

import pytest

from assistant.corpus import Corpus
from assistant.textnorm import match_key
from citation_check import (ANSWER_SCHEMA, CITE_DELIM, CITE_START, CITE_STOP, PAGE_ID_PATTERN, anchors,
                            cite_key, keyed, parse_inline_answer, schema_problems, seen_pages, verify_answer)

CORPUS_DIR = Path("corpus")

# What read_pages returned during one simulated conversation (three tool calls).
READ_CALLS = [
    ["2020-p057L", "2020-p057R", "2020-p006R"],
    ["2021-p112L", "2021-p112R", "2021-p134R", "2021-p999L", "2020-p001L"],   # last two: not_found, not_citable
    ["2022-p025L", "2022-p146R", "2023-p144L", "2024-p153R", "2025-p121L"],
]


@pytest.fixture(scope="module")
def corpus():
    return Corpus(CORPUS_DIR)


@pytest.fixture(scope="module")
def reads(corpus):
    return [corpus.read_pages(ids) for ids in READ_CALLS]


def check(corpus, reads, page_id, quote, text="문장.", **kw):
    answer = {"status": "answered", "sentences": [{"text": text, "citations": [{"page_id": page_id, "quote": quote}]}]}
    sentence = verify_answer(answer, corpus, reads, **kw)["sentences"][0]
    return sentence, sentence["citations"][0]


# id, cited page_id, quote, expected sentence grade, expected quote_status
CASES = [
    # true quotes: middle dot, numbers, parentheses
    ("true_dot_num_paren_2020", "2020-p057L", "제13차 한\u00b7중앙아 협력포럼(11.25, 서울)에서 코로나19 대응 경험을 공유하고", "verified", "exact"),
    ("true_quote_marks_2021", "2021-p112R", "국립외교원(KNDA)은 2021년 \u2018제8회 외교관후보자 정규과정\u2019을 약 46주 동안 운영했다", "verified", "exact"),
    ("true_list_parens_2022", "2022-p025L", "전략국제문제연구소(CSIS), 윌슨센터, 애틀란틱카운슬, 카네기재단, 미 외교정책협회(AFPC)", "verified", "exact"),
    # quote spanning a line break between paragraphs / table lines
    ("linebreak_paragraphs_2020", "2020-p057L", "추진했다. 이밖에도 제13차 한\u00b7중앙아 협력포럼", "verified", "exact"),
    ("linebreak_table_2021", "2021-p134R", "7.29~30 제10차 한\u00b7미\u00b7일(KNDA-CEIP-JIIA) 3자 회의 (웨비나)", "verified", "exact"),
    ("linebreak_after_hyphen_2024", "2024-p153R", "제10차 국립외교원(KNDA)-중국현대국제관계연구원(CICIR) 연례회의", "verified", "exact"),
    # hyphen / space / dot variants
    ("hyphen_as_is_2021", "2021-p134R", "제10차 한\u00b7미\u00b7일(KNDA-CEIP-JIIA) 3자 회의", "verified", "exact"),
    ("hyphen_as_space_2021", "2021-p134R", "제10차 한미일(KNDA CEIP JIIA) 3자 회의", "verified", "exact"),
    ("hyphen_as_endash_2021", "2021-p134R", "제10차 한\u00b7미\u00b7일(KNDA\u2013CEIP\u2013JIIA) 3자 회의", "verified", "exact"),
    ("hyphen_removed_2021", "2021-p134R", "제10차 한\u00b7미\u00b7일(KNDACEIPJIIA) 3자 회의", "verified", "exact"),
    ("dot_hangul_araea_2021", "2021-p134R", "제10차 한\u318d미\u318d일(KNDA-CEIP-JIIA) 3자 회의", "verified", "exact"),
    ("dot_as_period_near_2021", "2021-p134R", "제10차 한.미.일(KNDA-CEIP-JIIA) 3자 회의", "near", "near"),
    ("minus_ascii_for_endash_2020", "2020-p006R", "경제성장률은 미국 -3.5%, 유로존 -6.6%를 기록하는 등", "verified", "exact"),
    ("minus_dropped_rejected_2020", "2020-p006R", "경제성장률은 미국 3.5%, 유로존 6.6%를 기록하는 등", "unsupported", "not_found"),
    ("tilde_variant_2022", "2022-p146R", "한\u00b7캄보디아 2022년~2026년 EDCF 기본약정", "verified", "exact"),
    ("prime_quotes_arrow_2023", "2023-p144L", "소폭 증가('22.12월 165명 -> '23.12월 175명)", "verified", "exact"),
    ("corner_brackets_2025", "2025-p121L", "20명 규모의 \u300c제7기 대학생 서포터스(큰다(KNDA) 서포터스)\u300d를 선발하여", "verified", "exact"),
    ("brackets_swapped_2025", "2025-p121L", "20명 규모의 \u2018제7기 대학생 서포터스\uff08큰다\uff08KNDA\uff09 서포터스\uff09\u2019를 선발하여", "verified", "exact"),
    # lightly altered quotes
    ("altered_ending_near_2021", "2021-p112R", "국립외교원(KNDA)은 2021년 \u2018제8회 외교관후보자 정규과정\u2019을 약 46주 동안 운영하였다", "near", "near"),
    ("altered_range_sign_near_2024", "2024-p153R", "2024 서울국제법아카데미 7.1~12, 국립외교원", "near", "near"),
    ("altered_number_rejected_2021", "2021-p112R", "교육생 총 46명(일반 외교 44명, 지역 외교 2명)", "unsupported", "not_found"),
    ("paraphrase_rejected_2021", "2021-p112R", "교육생 47명이 공직소명의식, 전문지식, 실무역량, 외국어 등 4개 분야 교육과정을 이수했다", "unsupported", "not_found"),
    ("ellipsis_rejected_2021", "2021-p112R", "국립외교원(KNDA)은 \u2026 약 46주 동안 운영했다", "unsupported", "not_found"),
    ("too_short_2020", "2020-p057L", "서울", "unsupported", "too_short"),
    # quote over the L/R page break, both halves read
    ("page_break_joined_2020", "2020-p057L", "12월에는 제14차 한\u00b7러 극동시베리아 분과위원회를 화상 개최해", "verified", "joined"),
    # wrong / unread / invented page ids
    ("wrong_page_read_2021", "2021-p112L", "교육생 총 47명(일반 외교 44명, 지역 외교 3명)", "verified", "exact_on_other_page"),
    ("unread_real_page_2022", "2022-p025R", "Consultation Group)를 4년 8개월 만에 재가동하고", "unsupported", "page_rejected"),
    ("unread_not_citable_2020", "2020-p001L", "제13차 한\u00b7중앙아 협력포럼(11.25, 서울)", "verified", "exact_on_other_page"),
    ("invented_id_true_quote_2023", "2023-p999L", "등록 외신기자를 대상 백그라운드브리핑을 총 22회 실시하였다", "verified", "exact_on_other_page"),
    ("invented_id_fake_quote_2023", "2023-p999L", "외신기자를 대상으로 브리핑을 총 30회 실시하였다", "unsupported", "page_rejected"),
    ("malformed_id_2023", "2023년 286쪽", "대변인 정례 브리핑(총 100회)", "verified", "exact_on_other_page"),
]


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_quote_cases(corpus, reads, case):
    name, page_id, quote, grade, quote_status = case
    sentence, cit = check(corpus, reads, page_id, quote)
    print(f"\nCASE {name}: cited={page_id} -> grade={sentence['grade']} ({sentence['badge']}), "
          f"quote_status={cit['quote_status']}, id_status={cit['id_status']}, similarity={cit['similarity']}, "
          f"found_on={cit['found_on']}, label={cit['label']!r}, evidence={cit['evidence']!r}, "
          f"missing_anchors={cit['missing_anchors']}")
    assert (sentence["grade"], cit["quote_status"]) == (grade, quote_status)
    if cit["valid"]:
        assert cite_key(quote) in cite_key(cit["evidence"]) or cit["quote_status"] == "near"
        page_ids = cit["evidence_page_ids"]
        assert all(pid in seen_pages(reads) for pid in page_ids)
        assert cit["label"].startswith(f"{corpus.pages[page_ids[0]]['year']}년치 \u00b7 \u300c")


def test_old_gold_needle_breaks_with_match_key_but_not_cite_key(corpus):
    page = corpus.pages["2021-p134R"]["text"]
    assert match_key("KNDA-CEIP-JIIA") in match_key(page)
    assert match_key("KNDACEIPJIIA") not in match_key(page)       # the gold check that broke
    assert cite_key("KNDACEIPJIIA") in cite_key(page)
    assert cite_key("KNDA CEIP JIIA") in cite_key(page)


def test_near_evidence_is_original_text(corpus, reads):
    _, cit = check(corpus, reads, "2021-p112R", CASES[18][2])
    assert "운영했다" in cit["evidence"] and "운영하였다" not in cit["evidence"]
    assert cit["similarity"] >= 0.85
    _, cit = check(corpus, reads, "2024-p153R", CASES[19][2])
    assert "7.1-12" in cit["evidence"]


def test_near_can_be_switched_off(corpus, reads):
    sentence, cit = check(corpus, reads, "2021-p112R", CASES[18][2], accept_near=False)
    assert sentence["badge"] == "근거 없음" and cit["quote_status"] == "near" and not cit["valid"]


def test_changed_sign_or_number_is_reported(corpus, reads):
    _, cit = check(corpus, reads, "2020-p006R", "경제성장률은 미국 3.5%, 유로존 6.6%를 기록하는 등")
    assert cit["similarity"] >= 0.85 and cit["missing_anchors"] == ["3", "6"]
    _, cit = check(corpus, reads, "2021-p112R", "교육생 총 46명(일반 외교 44명, 지역 외교 2명)")
    assert cit["missing_anchors"] == ["2", "46"]


def test_known_limit_hangul_word_swap_is_only_near(corpus, reads):
    # A swapped Hangul place/country word keeps numbers and Latin words, so it lands in "near"
    # (badge "원문과 조금 다름"), never "확인됨"; the differences list shows what changed.
    quote = "코로나19 대응 경험을 공유하고, 한반도 평화프로세스에 대한 동남아시아 국가들의 지지를"
    sentence, cit = check(corpus, reads, "2020-p057L", quote)
    print("\nWORD_SWAP", sentence["grade"], cit["similarity"], cit["differences"], cit["evidence"])
    assert sentence["grade"] == "near" and cit["similarity"] >= 0.85
    assert ["중앙", "동남"] in cit["differences"]
    assert "중앙아시아" in cit["evidence"]


def test_many_changed_characters_are_not_near(corpus, reads):
    quote = "외교관후보자 정규과정 수강생 총 47명(일반 외교 44명, 지역 외교 3명)이 공직윤리의식, 전문학식, 실무능력"
    sentence, cit = check(corpus, reads, "2021-p112R", quote)
    print("\nMANY_CHANGES", sentence["grade"], cit["quote_status"], cit["similarity"], cit["differences"])
    assert sentence["grade"] == "unsupported" and cit["quote_status"] == "not_found"
    assert cit["similarity"] >= 0.85 and sum(max(len(a), len(b)) for a, b in cit["differences"]) > 6


def test_quote_with_literal_newline(corpus, reads):
    quote = "추진했다." + chr(10) + "이밖에도 제13차 한" + chr(0xB7) + "중앙아 협력포럼"
    sentence, cit = check(corpus, reads, "2020-p057L", quote)
    assert (sentence["grade"], cit["quote_status"]) == ("verified", "exact")


def test_wrong_page_not_fixed_when_disabled(corpus, reads):
    sentence, cit = check(corpus, reads, "2021-p112L", "교육생 총 47명(일반 외교 44명, 지역 외교 3명)", fix_wrong_page=False)
    assert sentence["badge"] == "근거 없음"
    assert cit["found_on"] == "2021-p112R" and cit["quote_status"] == "not_found" and not cit["corrected"]
    sentence, cit = check(corpus, reads, "2023-p999L", "등록 외신기자를 대상 백그라운드브리핑을 총 22회 실시하였다", fix_wrong_page=False)
    assert sentence["badge"] == "근거 없음" and cit["id_status"] == "unknown" and cit["found_on"] == "2023-p144L"


def test_page_break_needs_both_halves_read(corpus, reads):
    only_left = [corpus.read_pages(["2020-p057L"])]
    sentence, cit = check(corpus, only_left, "2020-p057L", "12월에는 제14차 한\u00b7러 극동시베리아 분과위원회를 화상 개최해")
    assert sentence["grade"] == "unsupported" and cit["quote_status"] == "not_found"
    _, cit = check(corpus, reads, "2020-p057L", "12월에는 제14차 한\u00b7러 극동시베리아 분과위원회를 화상 개최해")
    assert cit["evidence_page_ids"] == ["2020-p057L", "2020-p057R"]
    assert cit["label"] == "2020년치 \u00b7 \u300c2021 외교백서\u300d 110쪽 ~ 111쪽"


def test_only_pages_returned_by_read_pages_count(corpus, reads):
    seen = seen_pages(reads)
    assert "2021-p999L" not in seen and "2020-p001L" not in seen      # not_found / not_citable
    assert reads[1]["not_found"] == ["2021-p999L"] and reads[1]["not_citable"] == ["2020-p001L"]
    assert len(seen) == 11


def test_sentence_without_citation_and_references(corpus, reads):
    answer = {"status": "answered", "sentences": [
        {"text": "교육생은 47명이었습니다.", "citations": [
            {"page_id": "2021-p777R", "quote": "교육생 총 47명"},
            {"page_id": "2021-p112R", "quote": "교육생 총 47명(일반 외교 44명, 지역 외교 3명)"}]},
        {"text": "그중 44명은 일반 외교 분야였습니다.", "citations": [
            {"page_id": "2021-p112R", "quote": "교육생 총 47명(일반 외교 44명, 지역 외교 3명)"}]},
        {"text": "정리하면 다음과 같습니다.", "citations": []},
    ]}
    result = verify_answer(answer, corpus, reads)
    grades = [(s["grade"], s["badge"], s["refs"]) for s in result["sentences"]]
    print("\nREFS", grades, result["references"])
    assert grades == [("verified", "확인됨", [1]), ("verified", "확인됨", [1]), ("unsupported", "근거 없음", [])]
    assert result["sentences"][0]["citations"][0]["id_status"] == "unknown"
    assert len(result["references"]) == 1 and result["references"][0]["label"].endswith("221쪽")
    assert result["counts"] == {"verified": 2, "unsupported": 1} and result["status"] == "answered"


def test_inline_markers_design_c(corpus, reads):
    m = lambda *ids: CITE_START + "cite" + "".join(CITE_DELIM + i for i in ids) + CITE_STOP
    text = ("국립외교원은 약 46주 동안 정규과정을 운영했습니다." + m("2021-p112R") +
            " 교육생은 47명이었습니다." + m("2021-p112R", "2021-p112L") +
            " 이는 역대 최대 규모였습니다. 수료생은 50명이었습니다." + m("2021-p112R") +
            " 회의는 제10차였습니다." + m("2023-p999L"))
    answer = parse_inline_answer(text)
    assert [s["text"] for s in answer["sentences"]] == [
        "국립외교원은 약 46주 동안 정규과정을 운영했습니다.", "교육생은 47명이었습니다.",
        "이는 역대 최대 규모였습니다.", "수료생은 50명이었습니다.", "회의는 제10차였습니다."]
    result = verify_answer(answer, corpus, reads)
    for s in result["sentences"]:
        print("\nINLINE", s["text"], s["grade"], s["badge"],
              [(c["page_id"], c["id_status"], c["missing_anchors"], c["evidence"]) for c in s["citations"]])
    assert [s["grade"] for s in result["sentences"]] == ["page_only", "page_only", "unsupported", "page_only", "unsupported"]
    assert result["sentences"][3]["citations"][0]["missing_anchors"] == ["50"]      # only numbers/Latin are checkable
    assert "46주" in result["sentences"][0]["citations"][0]["evidence"]


def test_inline_marker_inside_long_sentence():
    text = "한\u00b7미는 확장억제를 강화했고," + CITE_START + "cite" + CITE_DELIM + "2022-p025R" + CITE_STOP + " 협의체를 재가동했다."
    answer = parse_inline_answer(text)
    assert [s["text"] for s in answer["sentences"]] == ["한\u00b7미는 확장억제를 강화했고, 협의체를 재가동했다."]
    assert answer["sentences"][0]["citations"] == [{"page_id": "2022-p025R", "quote": None}]


def test_keyed_positions_agree_with_cite_key_on_every_citable_page(corpus):
    checked = 0
    for page in corpus.pages.values():
        if not page["citable"]:
            continue
        disp, key, pos = keyed(page["text"])
        assert key == cite_key(page["text"]), page["page_id"]
        assert len(pos) == len(key) and all(0 <= p < len(disp) for p in pos)
        checked += 1
    assert checked == 1979


def test_cite_key_only_adds_folding_to_match_key(corpus):
    strip = {ord(c): None for c in "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe63\uff0d\u00b7'\"`\u00b4\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u2032\u2033\u2035\u2036\u300c\u300d\u300e\u300f\u3008\u3009\u300a\u300b\u00ab\u00bb<>"}
    strip.update({ord(c): "~" for c in "\u223c\uff5e\u301c"})
    for page in corpus.pages.values():
        if page["citable"] and "->" not in page["text"] and "=>" not in page["text"]:
            assert cite_key(page["text"]).replace("-", "") == match_key(page["text"]).translate(strip), page["page_id"]


def test_sources_hold_no_literal_special_characters():
    # Tool-written files turned escape sequences into literal characters once already (see citations.md).
    here = Path(__file__).parent
    for name in ("citation_check.py", "test_citation_check.py"):
        text = (here / name).read_text(encoding="utf-8")
        odd = sorted({hex(ord(c)) for c in text if ord(c) > 127 and not 0xAC00 <= ord(c) <= 0xD7A3})
        assert odd == [], (name, odd)


def test_anchors():
    assert anchors("미국 \u20133.5%, 7.1-12, KNDA-CEIP") == anchors("미국 -3.5% 7.1~12 knda ceip")
    assert anchors("미국 3.5%") != anchors("미국 \u20133.5%")


def test_answer_schema_is_strict_compatible_and_pattern_fits_corpus(corpus):
    assert schema_problems(ANSWER_SCHEMA) == []
    assert all(re.match(PAGE_ID_PATTERN, pid) for pid in corpus.pages)
    assert not re.match(PAGE_ID_PATTERN, "2023년 286쪽")
