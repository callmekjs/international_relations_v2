"""Page-level Korean BM25 search prototype for the white-paper assistant.

API (as requested):
    build_index(pages: list[dict], tokenizer='bigram', ...) -> SearchIndex
    search(index, query: str, years: list[int] | None = None, k: int = 10, balance_years=False) -> list[dict]
    save_index(index, dir) / load_index(dir)   (bm25s native files + pickle of page metadata/texts)

Recommended configuration (see results.md): tokenizer='bigram', backend='bm25s', k1=1.5, b=0.75,
year filter as a mask, balance_years=True when the caller compares 2-5 specific years.

`pages` rows need at least: page_id, year, text. Optional: chapter, printed_page, source_file.

Tokenizers
    kiwi      Kiwi content morphemes: NNG NNP NR VV VA XR SL SH SN (+W_SERIAL), light stoplist
    kiwi_dc   kiwi + Hangul bigrams of long noun tokens (>=4 syllables) to undo dictionary compounds
              such as 핵안보정상회의 / 경제협력개발기구
    kiwi_n    kiwi without verb/adjective stems (nouns, roots, foreign words, numbers only)
    bigram    Hangul/Hanja runs -> character bigrams (whitespace between Hangul removed first,
              so space-lost and spaced text tokenize the same); Latin words and numbers whole
    ws        whitespace tokens (eojeol), punctuation stripped, lower-cased
    kiwi_bi   one index holding both kiwi morphemes and '§'-prefixed bigrams (BM25 sums over both)
    hybrid:<a>+<b>[:rrf|:minmax]   score fusion of two sub-indexes (default rrf)

Backends: bm25s (default, sparse matrix, method='lucene', k1=1.5, b=0.75) or rank_bm25 (BM25Okapi).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np

# --------------------------------------------------------------------------- text normalisation
_DOTS = re.compile('[·ㆍ・･•‧∙⋅]')
_WRAP = re.compile(r'(?<=[가-힣])\n(?=[가-힣])')          # PDF line wrapped inside a word
_ABBR = re.compile(r'(?<![가-힣])[가-힣](?:[·\-][가-힣](?![가-힣]))+')  # 한·미·일, 한-중 -> 한미일, 한중
_WS = re.compile(r'\s+')


def clean(text: str) -> str:
    t = unicodedata.normalize('NFC', text or '').replace('₩', '·')   # 2008-2009 render '·' as '₩'
    t = _DOTS.sub('·', t)
    t = _WRAP.sub('', t)
    t = _ABBR.sub(lambda m: m.group(0).replace('·', '').replace('-', ''), t)
    return _WS.sub(' ', t).strip()


# --------------------------------------------------------------------------- tokenizers
_KIWI = None
_KEEP = {'NNG', 'NNP', 'NR', 'VV', 'VA', 'XR', 'SL', 'SH', 'SN', 'W_SERIAL'}
_KEEP_N = _KEEP - {'VV', 'VA'}
_STOP = {'하', '있', '되', '없', '않', '같', '보', '주', '알', '말', '어떻', '그렇', '이렇', '받', '대하', '위하', '통하', '따르'}
_HANGUL_RUN = re.compile(r'[가-힣]+')


def get_kiwi():
    global _KIWI
    if _KIWI is None:
        from kiwipiepy import Kiwi
        import os
        _KIWI = Kiwi(num_workers=int(os.environ.get('KIWI_WORKERS', '-1')))
        _KIWI.tokenize('')  # finish lazy init
    return _KIWI


def _kiwi_tokens(texts, keep, decompound=False):
    kiwi = get_kiwi()
    out = []
    for toks in kiwi.tokenize([clean(t) for t in texts]):
        doc = []
        for tk in toks:
            tag = tk.tag.split('-')[0]
            if tag not in keep:
                continue
            form = tk.form.lower()
            if form in _STOP:
                continue
            doc.append(form)
            if decompound and tag in ('NNG', 'NNP') and len(form) >= 4 and _HANGUL_RUN.fullmatch(form):
                doc.extend(form[i:i + 2] for i in range(len(form) - 1))
        out.append(doc)
    return out


_BIG_JOIN = re.compile(r'(?<=[가-힣])\s+(?=[가-힣])')
_BIG_RUNS = re.compile(r'[가-힣]+|[一-鿿]+|[a-z]+|\d+')


def _bigram_one(text):
    t = _BIG_JOIN.sub('', clean(text).lower())
    doc = []
    for m in _BIG_RUNS.finditer(t):
        s = m.group(0)
        c = s[0]
        if ('가' <= c <= '힣') or ('一' <= c <= '鿿'):
            if len(s) == 1:
                doc.append(s)
            else:
                doc.extend(s[i:i + 2] for i in range(len(s) - 1))
        else:
            doc.append(s)
    return doc


_PUNCT_EDGE = re.compile(r'^[\W_]+|[\W_]+$')


def _ws_one(text):
    return [w for w in (_PUNCT_EDGE.sub('', x) for x in clean(text).lower().split(' ')) if w]


def tokenize(texts: list[str], tokenizer: str) -> list[list[str]]:
    if tokenizer == 'kiwi':
        return _kiwi_tokens(texts, _KEEP)
    if tokenizer == 'kiwi_dc':
        return _kiwi_tokens(texts, _KEEP, decompound=True)
    if tokenizer == 'kiwi_n':
        return _kiwi_tokens(texts, _KEEP_N)
    if tokenizer == 'bigram':
        return [_bigram_one(t) for t in texts]
    if tokenizer == 'ws':
        return [_ws_one(t) for t in texts]
    if tokenizer in ('kiwi_bi', 'kiwi_dc_bi'):
        base = _kiwi_tokens(texts, _KEEP, decompound=tokenizer == 'kiwi_dc_bi')
        return [k + ['§' + g for g in _bigram_one(t)] for k, t in zip(base, texts)]
    raise ValueError('unknown tokenizer %r' % tokenizer)


# --------------------------------------------------------------------------- index
@dataclass
class SearchIndex:
    tokenizer: str
    meta: list            # per page: page_id, year, chapter, printed_page, source_file
    texts: list           # cleaned page text (for snippets)
    years: np.ndarray
    backend: str = 'bm25s'
    engine: object = None  # bm25s.BM25 or rank_bm25.BM25Okapi
    subs: list = field(default_factory=list)
    fusion: str = 'rrf'

    def scores(self, query: str) -> np.ndarray:
        q = tokenize([query], self.tokenizer)[0]
        if not q:
            return np.zeros(len(self.meta), dtype=np.float32)
        if self.backend == 'bm25s':
            return self.engine.get_scores(q)
        return np.asarray(self.engine.get_scores(q), dtype=np.float32)


def build_index(pages: list[dict], tokenizer: str = 'bigram', backend: str = 'bm25s',
                k1: float = 1.5, b: float = 0.75, show_progress: bool = False) -> SearchIndex:
    meta = [{k: p.get(k) for k in ('page_id', 'year', 'chapter', 'printed_page', 'source_file')} for p in pages]
    years = np.array([int(p['year']) if str(p['year']).isdigit() else -1 for p in pages], dtype=np.int32)
    texts = [clean(p['text']) for p in pages]
    if tokenizer.startswith('hybrid:'):
        spec = tokenizer.split(':', 1)[1]
        fusion = 'rrf'
        if ':' in spec:
            spec, fusion = spec.split(':')
        subs = [build_index(pages, t, backend, k1, b, show_progress) for t in spec.split('+')]
        return SearchIndex(tokenizer, meta, texts, years, backend, None, subs, fusion)
    corpus_tokens = tokenize([p['text'] for p in pages], tokenizer)
    # an empty page must still be a row; bm25s needs >=1 token overall
    if backend == 'bm25s':
        import bm25s
        engine = bm25s.BM25(k1=k1, b=b, method='lucene')
        engine.index(corpus_tokens, show_progress=show_progress)
    elif backend == 'rank_bm25':
        from rank_bm25 import BM25Okapi
        engine = BM25Okapi([t if t else [''] for t in corpus_tokens], k1=k1, b=b)
    else:
        raise ValueError(backend)
    return SearchIndex(tokenizer, meta, texts, years, backend, engine)


def _snippet(text: str, query: str, width: int = 150) -> str:
    """Window of ~width chars around the first query word found in the page (falls back to page start)."""
    words = sorted({w for w in re.split(r'\W+', clean(query)) if len(w) >= 2}, key=len, reverse=True)
    pos = -1
    for w in words:
        for cand in (w, w[:-1] if len(w) >= 3 else w):   # drop a trailing particle-ish syllable
            pos = text.find(cand)
            if pos >= 0:
                break
        if pos >= 0:
            break
    start = 0 if pos < 0 else max(0, pos - width // 3)
    return text[start:start + width]


def _topk(scores: np.ndarray, mask: np.ndarray | None, k: int) -> list[tuple[int, float]]:
    s = scores.astype(np.float32, copy=True)
    if mask is not None:
        s[~mask] = -np.inf
    k = min(k, int(np.isfinite(s).sum()))
    if k <= 0:
        return []
    idx = np.argpartition(-s, k - 1)[:k]
    idx = idx[np.argsort(-s[idx], kind='stable')]
    return [(int(i), float(s[i])) for i in idx if s[i] > 0]


def _ranked(index: SearchIndex, query: str, mask, depth: int) -> list[tuple[int, float]]:
    if not index.subs:
        return _topk(index.scores(query), mask, depth)
    fused = {}
    for sub in index.subs:
        ranked = _topk(sub.scores(query), mask, max(100, depth))
        if not ranked:
            continue
        if index.fusion == 'rrf':
            for r, (i, _) in enumerate(ranked):
                fused[i] = fused.get(i, 0.0) + 1.0 / (60 + r + 1)
        else:  # minmax on the retrieved list
            hi, lo = ranked[0][1], ranked[-1][1]
            for i, sc in ranked:
                fused[i] = fused.get(i, 0.0) + ((sc - lo) / (hi - lo) if hi > lo else 1.0)
    return sorted(fused.items(), key=lambda x: -x[1])[:depth]


def search(index: SearchIndex, query: str, years: list[int] | None = None, k: int = 10,
           balance_years: bool = False) -> list[dict]:
    """Top-k pages. years=None searches everything. balance_years=True (only matters when several years
    are given) interleaves the per-year rankings round-robin so every requested year is represented."""
    mask = np.isin(index.years, years) if years else None
    if balance_years and years and len(set(years)) > 1:
        per = {y: _ranked(index, query, index.years == y, k) for y in sorted(set(years))}
        hits, r = [], 0
        while len(hits) < k and any(r < len(v) for v in per.values()):
            for y in sorted(per):
                if r < len(per[y]) and len(hits) < k:
                    hits.append(per[y][r])
            r += 1
    else:
        hits = _ranked(index, query, mask, k)
    out = []
    for rank, (i, sc) in enumerate(hits, 1):
        row = dict(index.meta[i])
        row.update(rank=rank, score=round(sc, 4), snippet=_snippet(index.texts[i], query))
        out.append(row)
    return out


def save_index(index: SearchIndex, path: str) -> None:
    """bm25s native save for the engine (+ pickle of metadata). Only for non-hybrid bm25s indexes."""
    import os, pickle
    os.makedirs(path, exist_ok=True)
    index.engine.save(os.path.join(path, 'bm25s'), show_progress=False)
    with open(os.path.join(path, 'meta.pkl'), 'wb') as f:
        pickle.dump(dict(tokenizer=index.tokenizer, meta=index.meta, texts=index.texts, years=index.years), f)


def load_index(path: str) -> SearchIndex:
    import os, pickle, bm25s
    with open(os.path.join(path, 'meta.pkl'), 'rb') as f:
        d = pickle.load(f)
    engine = bm25s.BM25.load(os.path.join(path, 'bm25s'), show_progress=False)
    return SearchIndex(d['tokenizer'], d['meta'], d['texts'], d['years'], 'bm25s', engine)


if __name__ == '__main__':
    import json, sys, time
    corpus = sys.argv[1] if len(sys.argv) > 1 else 'corpus_split.jsonl'
    tok = sys.argv[2] if len(sys.argv) > 2 else 'bigram'
    pages = [json.loads(l) for l in open(corpus, encoding='utf-8')]
    t = time.time(); idx = build_index(pages, tok); print('built %s on %d pages in %.1fs' % (tok, len(pages), time.time() - t))
    for q in sys.argv[3:] or ['한미 정상회담 미사일 지침 종료']:
        for h in search(idx, q, None, 5):
            print(h['rank'], h['page_id'], h['printed_page'], round(h['score'], 2), h['snippet'][:80])
