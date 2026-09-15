"""Character normalisation shared by search now and by the table/compare cell check later."""
from __future__ import annotations

import re
import unicodedata

_SOFT_HYPHEN = re.compile("\u00ad\n?")
_INVISIBLE = re.compile("[\x07\x08\u200b\u200c\u200d\ufeff]")
_SPACES = re.compile("[\u3000\u00a0 \t]")
_DOTS = re.compile("[\u318d\u30fb\uff65\u2027\u2219\u22c5\u2022\u2024\u0387\uf09e\u00b7]")
_HANGUL_GAP = re.compile(r"(?<=[가-힣])[\s\u00b7]+(?=[가-힣])")
_RUNS = re.compile(r"[가-힣]+|[一-鿿]+|[a-z]+|\d+")
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFC; soft hyphens and invisible characters removed; dot variants unified to '·';
    all whitespace collapsed to single spaces (one line, for snippets)."""
    t = unicodedata.normalize("NFC", text or "")
    t = _SOFT_HYPHEN.sub("", t)
    t = _INVISIBLE.sub("", t)
    t = _SPACES.sub(" ", t)
    t = _DOTS.sub("\u00b7", t)
    return _WS.sub(" ", t).strip()


def match_key(text: str) -> str:
    """Comparison form: normalized, lower-cased, no whitespace, no '·' between Hangul."""
    return _WS.sub("", _HANGUL_GAP.sub("", normalize(text).lower()))


def utf8_safe(value):
    """Every lone surrogate in a string, or in the strings of a JSON-like list or dict, becomes '?'.
    json.loads turns a surrogate escape in model-written JSON into one, and records and the terminal
    are written as UTF-8, which cannot hold it."""
    if isinstance(value, str):
        return value.encode("utf-8", "replace").decode("utf-8")
    if isinstance(value, list):
        return [utf8_safe(item) for item in value]
    if isinstance(value, dict):
        return {utf8_safe(key): utf8_safe(item) for key, item in value.items()}
    return value


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
