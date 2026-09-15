from assistant.textnorm import bigram_tokens, match_key, normalize


def test_dot_variants_become_middle_dot():
    for variant in ("\u318d", "\uff65", "\u30fb", "\u2027", "\u2219", "\u2024", "\u0387", "\uf09e"):
        assert normalize(f"한{variant}미") == f"한\u00b7미"


def test_soft_hyphen_and_invisible_characters_removed():
    assert normalize(f"NA\u00ad\nTO 정상회의") == "NATO 정상회의"
    assert normalize(f"발행처\x07 외교부\u200b") == "발행처 외교부"


def test_whitespace_collapsed_to_one_line():
    assert normalize(f"첫 줄\n둘째\u3000줄\t끝") == "첫 줄 둘째 줄 끝"


def test_match_key_ignores_spaces_and_hangul_dots():
    assert match_key(f"한\u00b7아세안 협력") == match_key("한아세안협력") == "한아세안협력"
    assert match_key("G20 정상회의") == "g20정상회의"


def test_bigram_tokens():
    assert bigram_tokens("정상 회담") == ["정상", "상회", "회담"]
    assert bigram_tokens(f"한\u00b7아세안") == bigram_tokens("한아세안") == ["한아", "아세", "세안"]
    assert bigram_tokens("G20 정상회의 2023") == ["g", "20", "정상", "상회", "회의", "2023"]
    assert bigram_tokens("미") == ["미"]
    assert bigram_tokens("") == []
