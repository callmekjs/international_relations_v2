# Korean page-level search — choice and proof

Date 2026-09-14 · folder `scratchpad/plan1/search` · nothing written under `C:\international_relations`, no API calls, no git.

## 쉬운 요약 (주석님용)

| 물음 | 답 |
|---|---|
| 무엇으로 찾을까? | **글자 2개 단위(bigram) BM25**. 형태소 분석기 Kiwi는 안 써도 됩니다 |
| 왜? | 조수(Claude)가 넣을 법한 검색어로 시험하면 bigram이 49문항 중 정답 쪽을 상위 10위 안에 99~100% 찾았고, Kiwi(95%)보다 못하지 않았습니다. 설치가 간단하고 메모리도 1/3입니다 |
| 띄어쓰기가 사라진 2006년치는? | bigram·Kiwi 모두 괜찮음(90~100%). 띄어쓰기 단위로 쪼개는 방식만 무너짐(0~40%) |
| 설계서에서 바꿀 곳 | 4.1 "Kiwi 우선, 문제 있으면 bigram" → "bigram 기본" |

---

## 1. Versions and install (verified)

venv: `python -m venv venv` from Python 3.12.10 (MSC v.1943, AMD64), `pip install kiwipiepy bm25s rank_bm25` → log `pip_install.log`.

| package | version | distribution used on Windows / py3.12 | notes |
|---|---|---|---|
| bm25s | 0.3.11 | `bm25s-0.3.11-py3-none-any.whl` (74 kB) | `Requires: numpy` only; scipy and numba are **not** installed and not needed for the numpy backend (checked with `importlib.util.find_spec`) |
| rank_bm25 | 0.2.2 | `rank_bm25-0.2.2-py3-none-any.whl` | pure Python |
| kiwipiepy | 0.23.2 | `kiwipiepy-0.23.2-cp39-abi3-win_amd64.whl` (3.6 MB; `_kiwipiepy.pyd` 24.6 MB on disk) | LGPL v3; a manylinux2014 x86_64 abi3 wheel also exists (pip resolved its metadata for py3.10 and py3.12) |
| kiwipiepy_model | 0.23.0 | **sdist only** (`kiwipiepy_model-0.23.0.tar.gz`, 88.0 MB) → built locally to a py3-none-any wheel, no compiler needed, 26 s with `--no-cache-dir` | 105 MB installed. `pip install --only-binary=:all:` for manylinux **fails** ("No matching distribution found for kiwipiepy_model<0.24,>=0.23") |
| numpy | 2.5.3 | cp312 win_amd64 wheel | |
| tqdm / colorama | 4.70.1 / 0.4.6 | wheels | kiwipiepy deps |

All installs succeeded without errors. site-packages total 197 MB, of which Kiwi ≈ 130 MB.

Documentation facts checked in the installed sources:
- bm25s `BM25.index()` accepts "An iterable of documents, where each document is a list of tokens (strings)." (`venv/Lib/site-packages/bm25s/__init__.py` line 484). `get_scores(query_tokens_single, weight_mask=None)` (line 622) silently drops out-of-vocabulary tokens (`get_tokens_ids`, "leaving out tokens that are not in the vocabulary"), but indexes `query_tokens_single[0]` first, so an **empty token list raises IndexError** — the wrapper guards it. `save()`/`load()` write/read `.npy` arrays + JSON vocab (line 941/1130); save→load gave identical rankings (`reload_same_results: true` in every run).
- kiwipiepy `Kiwi.__init__` docstring (installed package): lazy initialisation — call `tokenize('')` to pre-initialise; `num_workers` "0으로 설정 시 단일 스레드에서 동작하며 async 기능을 지원하지 않습니다", `-1` = all cores. Verified consequence: with `num_workers=0`, `kiwi.tokenize(list_of_texts)` raises ``Exception: `asyncAnalyze` doesn't work at single thread mode``. Use `num_workers>=1` for batch tokenisation.

## 2. Test corpus (verified)

Survey text files are PyMuPDF `get_text('text')` output, one block per PDF page, header `===== [PDF p.N] =====`.

| corpus file | built by | unit | pages | chars |
|---|---|---|---|---|
| `corpus_split.jsonl` main set | `build_corpus.py` (PyMuPDF re-extraction from `data/`, read-only) | printed page: spread PDFs (2015, 2016, 2018, 2020–2025) cut into L/R halves with `clip`; `printed_page` guessed from `survey/pn_results.json` offsets | 4,631 | 3.78 M |
| `corpus_survey.jsonl` main set | survey text as-is | PDF page | 3,003 | 3.78 M |
| 2006 space-lost | survey text (PyMuPDF, spaces dropped) | PDF page | 304 | 0.23 M |
| 2006 restored | `pdfminer.six` `extract_pages` + `LAParams()` | PDF page | 304 | 0.27 M |

Main set = folders 2012–2016, 2018, 2020–2025. The space-lost test indexes **main + 2006** together (4,935 units), so 2006 pages compete with clean pages.

## 3. Method

Normalisation `clean()` (shared by all tokenizers): NFC; `₩`→`·`; middle-dot variants `·ㆍ・･•‧∙⋅`→`·` (2013 uses `ㆍ`, 2025 uses `･` — seen in the text); join a PDF line break between two Hangul syllables (Korean justified text wraps mid-word: "이끌\n어 왔다"); join single-syllable country chains `한·미·일`/`한-중` → `한미일`/`한중` so they match queries typed without dots; collapse whitespace.

Tokenizers (`search_proto.py`):
- `ws` — whitespace tokens (eojeol), edge punctuation stripped.
- `bigram` — whitespace **between Hangul removed first**, then character bigrams over Hangul/Hanja runs; Latin words and digit runs whole. Makes spaced and space-lost text tokenize identically.
- `kiwi` — Kiwi morphemes tagged NNG NNP NR VV VA XR SL SH SN W_SERIAL, small verb stoplist. Variants: `kiwi_n` (no VV/VA), `kiwi_dc` (+bigrams of ≥4-syllable nouns, to split dictionary compounds such as `핵안보정상회의`), `kiwi_bi` (one index with Kiwi tokens + `§`-prefixed bigrams).
- `hybrid:a+b` — two indexes, RRF (k=60) or min-max score fusion over each list's top 100.

BM25: bm25s `method='lucene'`, k1=1.5, b=0.75; year filter = boolean mask on the full score vector; `balance_years=True` interleaves per-year rankings.

Evaluation (`eval_queries.jsonl`, 49 queries): 39 main (29 single-fact, 5 multi-year with one gold group per year, 5 broad-topic) + 10 on 2006. Each has a natural visitor `question` (paraphrased, answer words avoided where the question asks for them) and a `keywords` string of the kind the assistant would send. Gold pages are resolved by **needles**: a page is gold if it contains all needle strings of a group (after `clean` and removal of spaces, dots, hyphens, quotes), optionally restricted to a year; this works on any page segmentation (`gold.py`; gold counts 1–18 per group, printed by `python gold.py`). Recall@k = mean over queries of (gold groups with ≥1 page in top k) / (groups). Four query settings: Q / KW × with / without year filter (+ balanced years). Each config ran in a fresh process; memory = Windows `PeakWorkingSetSize` (psapi); 24-thread desktop CPU.

## 4. Results (verified — full tables in `report_tables.md`, raw in `runs/*.json`)

### 4.1 Main set, printed-page units (4,631 pages, 39 queries). Numbers are %.

| config | Q+yr R@5 / R@10 | Q R@5 / R@10 | **KW+yr R@5 / R@10** | KW R@5 / R@10 | KW+yr balanced R@10 | MRR@10 KW+yr | build s | peak RAM MB | index MB | query ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| ws | 58 / 70 | 45 / 50 | 82 / 90 | 67 / 77 | 92 | 0.71 | 1.2 | 168 | 7.8 | 0.1 / 0.3 |
| **bigram** | 82 / 95 | 63 / 78 | **99 / 99** | 91 / 96 | **100** | 0.87 | 2.0 | **291** | 13.0 | 0.2 / 0.5 |
| kiwi | 85 / 95 | 69 / 82 | 94 / 95 | 85 / 90 | 96 | 0.83 | 2.8 (1 thread: 29.9) | 791 | 5.0 | 0.6 / 1.3 |
| kiwi_n | 86 / 97 | 73 / 88 | 94 / 95 | 85 / 90 | 96 | 0.83 | 2.6 | 804 | 4.9 | 1.1 / 1.8 |
| kiwi_dc | 87 / 95 | 67 / 82 | 95 / 95 | 86 / 90 | 96 | 0.87 | 2.7 | 814 | 5.9 | 0.9 / 1.4 |
| kiwi_bi | 87 / 94 | 69 / 78 | 99 / 99 | 90 / 96 | 100 | 0.88 | 4.2 (1 thread: 37.9) | 1,028 | 18.0 | 0.6 / 1.3 |
| hybrid kiwi+bigram RRF | 87 / 92 | 76 / 78 | 95 / 96 | 87 / 92 | 97 | 0.86 | 4.7 | 980 | — | 1.2 / 2.4 |
| hybrid kiwi+bigram min-max | 85 / 94 | 72 / 78 | 95 / 99 | 90 / 92 | 100 | 0.88 | 4.5 | 967 | — | 1.5 / 2.3 |
| kiwi on rank_bm25 | 85 / 90 | 69 / 82 | 95 / 95 | 86 / 91 | 96 | 0.83 | 2.1 | 797 | — | **12.3 / 20.9** |
| bigram on rank_bm25 | 82 / 95 | 63 / 74 | 99 / 99 | 96 / 99 | 100 | 0.87 | 1.5 | 250 | — | **28.1 / 55.6** |

One query = 2.6 points (29 fact queries: 3.4). Kiwi process after model load holds 565 MB before any index is built; Kiwi init 1.7–2.9 s; bm25s index load 0.1 s. PDF-page units (survey text) give the same ordering (bigram KW+yr 99/99, kiwi 94/96, kiwi Q+yr 95/97 because larger units are easier).

### 4.2 2006 queries (10) on main + 2006

| config | space-lost text: Q+yr R@5 / R@10 | space-lost: KW R@5 / R@10 | pdfminer-restored: Q+yr R@5 / R@10 | restored: KW R@5 / R@10 |
|---|---|---|---|---|
| ws | 0 / 10 | 10 / 10 | 80 / 90 | 50 / 60 |
| bigram | 90 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |
| kiwi | 100 / 100 | 90 / 100 | 100 / 100 | 90 / 100 |
| kiwi_dc | 100 / 100 | 90 / 100 | 100 / 100 | 90 / 100 |
| kiwi_bi | 100 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |
| hybrid RRF | 100 / 100 | 100 / 100 | 100 / 100 | 100 / 100 |

Space restoration matters only for `ws`. (Kiwi segments space-lost text well: `북한은미재무부가2005년9월15일마카오소재BDA 은행을…` → 북한/미/재무/부/2005/…/마카오/소재/BDA/은행.)

### 4.3 BM25 parameters (`sweep_results.md`)

k1 ∈ {0.9, 1.2, 1.5, 2.0} × b ∈ {0.4, 0.6, 0.75, 0.9}: bigram KW+yr R@10 stays 99 everywhere, Q+yr R@10 92–95; kiwi KW+yr R@10 95 everywhere. Defaults are fine; no tuning warranted on 39 queries.

### 4.4 Failure cases worth knowing (verified)

- **Kiwi context-dependent query segmentation.** Document text `한일중 정상회의` → token `한일중` (NNP), but the short query `한일중 정상회의 서울 개최 2024` → `['일', '정상', '회의', '서울', '개최', '2024']` (`한일중` dropped). Result (keyword query + year filter): q25 missed by kiwi, kiwi_dc and the RRF hybrid, m04's 2024 group missed by kiwi and kiwi_dc; bigram ranks them 3 and 1.
- **Kiwi dictionary compounds.** `핵안보정상회의`, `경제협력개발기구`, `세계보건기구` are single NNP tokens (also with `load_multi_dict=False`), while `핵안보 정상회의` → 핵/안보/정상/회의. `kiwi_dc` was meant to fix this; gain ≤ 1 query.
- **Multi-year with one ranked list.** m01 ("2012 and 2023"): with the keyword query and a plain year mask every config fills the top 10 with 2012 pages and misses 2023; `balance_years=True` fixes it (multi-year R@10: bigram 90→100, kiwi 80→90).
- **No year filter.** b05 "2024 ODA": without a filter all non-ws configs return other years' ODA pages. The assistant should pass years whenever the question names one.
- **Gold strictness.** q18 gold is the single page containing both 북미정상회담 and 센토사; other pages saying "6.12 싱가포르 북미정상회담" answer the question but are not counted, so all configs "miss" q18 in the Q setting.

## 5. Recommendation

**Use character-bigram BM25 on bm25s, one document per printed page** — i.e. flip the spec's §4.1 order (bigram primary, no Kiwi). Concretely:

1. `clean()` normalisation as in `search_proto.py` (NFC, `₩`, dot variants, wrapped-line join, `한·미`→`한미`), applied at index time and to queries; keep raw text in `corpus/pages.jsonl`. Reuse the same normaliser for the table/compare ✓/⚠ cell check.
2. `bigram` tokens, `bm25s.BM25(k1=1.5, b=0.75, method='lucene')`, persisted with `BM25.save()` into `corpus/index/` (≈13 MB for the main set; ≈25–30 MB for the whole first-phase corpus — *inferred* by linear scaling from 3.78 M → ~7–8 M chars) and loaded at Space start in ~0.1 s. Build in `prep/` (2 s, pure Python, single thread) or even at startup.
3. `search(index, query, years, k=10)`: year filter as a mask over the full score vector; when the caller gives 2–5 distinct years (compare, multi-year tasks) set `balance_years=True` so every year is represented.
4. Dependencies: `bm25s==0.3.11`, `numpy` only. Do not add kiwipiepy (saves ~130 MB install, ~565 MB RAM, 2–3 s init, an 88 MB sdist build, and the query-segmentation failure above). rank_bm25 has no advantage (20–140× slower queries: 12–28 ms vs 0.2–0.6 ms p50; different IDF variant, recall within ±2 queries).

Why: in the setting that matches the product (assistant-written keyword query + year filter) bigram reached R@5 99 / R@10 99 (balanced 100) vs kiwi 94 / 95; on raw natural-language questions the two tie at R@10 95 (kiwi +3 at R@5, i.e. one query); both are robust to lost spaces; bigram needs a third of the memory.

**Hybrid:** not proposed. `kiwi_bi` and min-max fusion match bigram within one query on KW settings and are ≤ 1–2 queries better only on raw-question R@5, at 3.5× the RAM and a Kiwi dependency — not a clear win. Revisit only if the gold-set search check (spec §8.1) shows misses that are morphological (e.g. verb forms) rather than wording differences.

## 6. Risks and limits

1. **Author bias in the eval.** I picked facts after reading the pages and wrote both questions and keywords; keywords may echo document wording, which favours exact lexical matching (bigram). Treat the numbers as a sanity check, not a benchmark. 49 queries: differences ≤ 2 queries are noise.
2. **Wording variants defeat any lexical index**: `한중일` vs `한일중` (both used in the books), `북미` vs `미북`, `사드` vs `THAAD`, `위안부 합의` vs `12·28 합의`. Mitigation (inferred): tell the assistant in the tool description to retry with synonyms / word-order variants; optionally a small alias expansion table.
3. **Untested text**: OCR output for 2017/2019 (bigrams should degrade gracefully with isolated character errors — inferred), other space-lost folders (2003–2005, 2007–2009, 2011, 참여정부), `₩` substitution on real 2008–2009 text, 참여정부 garbage running headers (will add noise tokens), appendix tables and chronologies (they rank well for date/number queries, which may crowd out narrative pages).
4. **Year semantics**: a volume's overview often mentions the next year's early events (the 2015 volume mentions the Feb 2016 Kaesong shutdown); a strict covered-year filter can hide valid pages.
5. **Page units**: spreads were cut at the geometric middle; text crossing the gutter or wide tables may be split. Printed page numbers here are guesses from survey offsets — the prep step owns the real mapping.
6. **Line-wrap join heuristic** also joins real boundaries at headings/table cells (e.g. `정상회담|이명박` → `정상회담이명박`); costs a few spurious bigrams.
7. **Snippet**: prototype returns ~150 chars around the first matched query word; the spec says "앞부분 약 150자" — decide which the tool should show.
8. **bm25s edge case**: `get_scores([])` raises IndexError; keep the empty-query guard. Pages with no text stay as rows with zero score.
9. Timings are from a 24-thread desktop; HF CPU Basic (2 vCPU) will be slower for Kiwi batch builds (1-thread Kiwi build: 30 s) but bigram is single-threaded Python already (2 s here).

## 7. Files

| file | purpose |
|---|---|
| `search_proto.py` | `build_index(pages, tokenizer='bigram', backend='bm25s')`, `search(index, query, years, k, balance_years=False)`, `save_index`/`load_index`, all tokenizers |
| `test_api.py` | API contract checks (dots, space-lost text, empty/OOV query, filter, balance, save/load) — passes |
| `eval_queries.jsonl` | 49 queries with question, keywords, years, needle-based gold groups |
| `gold.py`, `grep_pages.py` | gold resolution / needle grep over any corpus |
| `build_corpus.py` | builds the three corpora from survey text and `data/` PDFs (read-only) |
| `bench.py`, `report.py`, `sweep.py` | per-config benchmark in fresh processes, table generation, k1/b sweep |
| `report_tables.md`, `sweep_results.md`, `runs/*.json` | full metric tables, per-query first-gold ranks, timing/memory |
| `pip_install.log`, `venv/` | install record and the virtualenv |
