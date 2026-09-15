# Token counts and per-question cost: gpt-5.6-sol (vs terra, luna)

Measured 2026-09-15 for Plan 2 of "외교백서 AI 조수". All numbers below were produced by the scripts in this folder.
KRW at 1,400 per USD. Budget 20,000 KRW = $14.29.

## 0. Method

| Step | Script | What | Network |
|---|---|---|---|
| 1 | `extract_payloads.py` (project venv, read-only) | 50 random citable pages (seed 20260915), 8 real `Corpus.search(k=10)` results, 16 `read_pages` results (8 of 5 pages, 8 of 4 pages: top-5 and hits 6-9 of each search), `get_toc` for 6 years, largest main chapter per volume | none |
| 1b | `extract_all_chapters.py` + inline count -> `chapters_tokens.json` | every chapter's summary payload | none |
| 2 | `measure_local.py` -> `local_counts.json` | tiktoken 0.14.0 counts | none |
| 3 | `measure_api.py` -> `api_counts.json` | `POST /v1/responses/input_tokens` (42 calls, 41 OK, 1 HTTP 400; **0 generation calls**) | OpenAI counting endpoint only |
| 4 | `build_measurements.py` -> `measurements.json` | merged + derived constants | none |
| 5 | `cost_model.py` -> `cost_results.json`, `cost_model_output.txt` | cost simulation | none |

Tool outputs are serialised exactly as a `function_call_output.output` string would be: `json.dumps(obj, ensure_ascii=False, separators=(",", ":"))`.
The realistic developer prompt (1,184 text tokens) and 4 strict function tools (`search`, `read_pages`, `get_toc`, `report_status`) are in `prompt_assets.py`.
Git status of `C:\international_relations` was clean before and after.

The failed call (#26) tried `[user, function_call]` without an output: `400 "No tool output found for function call c."` It was not needed; the per-round overhead was derived from the growing-loop counts instead.

## 1. Tokenizer

**Verified: gpt-5.6-sol, terra and luna tokenize text exactly like tiktoken `o200k_base`.**

- No OpenAI doc page names the GPT-5.6 tokenizer (searched model pages, GPT-5.6 guide, upgrade guide, token-counting guide).
- tiktoken 0.14.0 has no explicit `gpt-5.6-*` entry. `tiktoken.encoding_for_model("gpt-5.6-sol")` resolves to `o200k_base` only through the prefix rule `MODEL_PREFIX_TO_ENCODING["gpt-5"]`. So on its own this was an inference.
- Empirical check against the counting endpoint (the API number minus the tiktoken number must stay constant if the tokenizers are the same):

| Test (calls) | tiktoken o200k_base | API `input_tokens` | API − tiktoken |
|---|---|---|---|
| 10 single pages, 20 to 925 tokens (10) | 20 … 925 | 26 … 931 | **+6 every time** |
| 50 sampled pages joined (sol, terra, luna) (3) | 27,428 | 27,434 / 27,434 / 27,434 | +6, same on all 3 models |
| 4 search outputs, 4 read_pages outputs, 1 toc, 1 ASCII-escaped search, each inside `[user, function_call, function_call_output]` (10) | 1,554 … 5,550 | 1,612 … 5,608 | **+58 every time** |
| 6 largest chapters inside `[developer(summary prompt 163), user(payload)]` (6) | body + 163 | 33,759 … 70,914 | **+10 every time** |

Structural overheads learned from these (not visible to tiktoken): +6 per request with a bare string input, +4 per developer message, +22 to 24 per tool round (function_call + function_call_output wrapper, excluding the arguments). Passing `reasoning.effort` low/medium/high did not change the count (1,630 each).

**Counting endpoint and billing.** The docs describe it but say nothing about billing:
> "Returns input token counts of the request." (https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens.md)
> "Token counting lets you determine how many input tokens a request will use before you send it to the model." (https://developers.openai.com/api/docs/guides/token-counting.md)

It generates nothing: the response holds only `object` and `input_tokens`. The pricing page has no line for it. **Whether it is billed is not documented.** I found no page saying free or billed. Web search found nothing official either.

## 2. Measured token sizes

### 2.1 Page text (Korean, 59% Hangul)

| Set | Pages | Tokens: mean | median | p90 | min | max | Tokens per char | Tokens per non-space char | Chars per token |
|---|---|---|---|---|---|---|---|---|---|
| Random sample (seed 20260915) | 50 | **548** | **591** | **748** | 20 | 925 | **0.638** | 0.810 | 1.57 |
| All citable pages | 1,979 | 570 | 584 | 759 | 20 | 1,738 | 0.634 | 0.800 | 1.58 |

- Hangul-only runs: 0.891 tokens per syllable.
- All citable text together is 1,128,110 tokens (text only).
- The API agrees with these numbers to within the constant +6.

### 2.2 Tool payloads (tiktoken; the API adds a constant wrapper, see section 1)

| Payload | n | Mean | Median | p90 | Max |
|---|---|---|---|---|---|
| `search` k=10 (compact JSON) | 8 queries | **1,821** | 1,816 | 1,891 | 1,926 |
| `read_pages` 5 pages | 8 | **3,191** | 3,124 | 3,653 | 3,985 |
| `read_pages` 4 pages | 8 | **2,511** | 2,537 | 2,839 | 3,111 |
| `get_toc(year)` | 6 | 1,618 | – | – | 1,718 |
| function_call arguments | – | search 18, read_pages(5 ids) 35, read_pages(4 ids) 29, get_toc 6 | | | |

Serialisation matters:

| Variant (search "한미 정상회담") | Tokens |
|---|---|
| `ensure_ascii=True` (Python default) | 5,550 (API 5,608−58). **2.9 times more** |
| `ensure_ascii=False`, compact | 1,926 |
| Mean over 8 searches: full payload | 1,821 |
| Without `label` | 1,582 |
| Without `label`, `score`, `year`, `section` | 1,278 |
| Snippets alone | 935 |

### 2.3 Prompt, tools and the measured loop (API)

| Item | Tokens (API) |
|---|---|
| 4 strict tool definitions (`prompt_assets.TOOLS`) | **419** (tiktoken of the JSON text is 551; the API renders tools more compactly) |
| Developer prompt draft (1,184 text tokens) | 1,188 |
| Question message (27 chars, 17 text tokens) | 23 |
| Request 1 = tools + developer + question | **1,630** |
| Request 2 = + search call and output (1,926) | **3,596** |
| Request 3 = + read_pages(5) call and output (3,226) | **6,881** |
| Request 4 = + read_pages(4) call and output (2,634) | **9,568** |

- The loop above has no reasoning items: they are opaque and cannot be built without generation.
- `cost_model.py` rebuilds this loop from the constants to within 1 token (calibration line in `cost_model_output.txt`).

### 2.4 Chapters (summary sizing)

Largest main chapter of each volume, sent as `[developer summary prompt, user chapter JSON]` (API):

| Year | Chapter | Pages | Chars | Input tokens (API) |
|---|---|---|---|---|
| 2020 | 제4장 외교지평 확대 | 93 | 82,127 | 56,381 |
| 2021 | 제4장 지역 외교 | 52 | 47,641 | 33,759 |
| 2022 | 제3장 인도-태평양 전략과 지역별 협력 네트워크 | 73 | 65,754 | 47,515 |
| **2023** | **제3장 인도-태평양 전략과 지역별 협력 네트워크** | **108** | **97,674** | **70,914** |
| 2024 | 제3장 인도-태평양 전략 및 지역별 협력 네트워크 | 102 | 83,704 | 61,457 |
| 2025 | 제3장 외교다변화를 통한 전략적 지평 확장 | 72 | 62,391 | 45,231 |

- The largest chapter (70.9K) is under the spec's 150K summary cap, under the 272K long-context threshold, and under the 922K maximum input.
- So **no section splitting is needed for token reasons.**
- All 7 main chapters of 2025 together: 157,691 payload tokens.
- Main-chapter totals per year are in `measurements.json` under `derived.main_chapters_payload_tokens_by_year`.
- Appendices (부록) run 38K to 56K tokens per year.

## 3. Prices (quoted)

Pricing page, Standard tier, per 1M tokens (https://developers.openai.com/api/docs/pricing.md):

| Model | Short input | Short cached input | Short cache writes | Short output | Long input | Long cached | Long cache writes | Long output |
|---|---|---|---|---|---|---|---|---|
| gpt-5.6-sol | $4.00 | $0.40 | $5.00 | $20.00 | $8.00 | $0.80 | $10.00 | $30.00 |
| gpt-5.6-terra | $2.00 | $0.20 | $2.50 | $12.00 | $4.00 | $0.40 | $5.00 | $18.00 |
| gpt-5.6-luna | $0.20 | $0.02 | $0.25 | $1.20 | $0.40 | $0.04 | $0.50 | $1.80 |

- **Threshold.** The HTML table's column tooltips say Short context "≤272K input tokens" and Long context ">272K input tokens" (https://developers.openai.com/api/docs/pricing).
- The model page says: "Prompts with >272K input tokens are priced at 2x input and 1.5x output for the full request." (https://developers.openai.com/api/docs/models/gpt-5.6-sol.md)
- Every request in this app is far below 272K, so **short-context prices apply**.
- **Promotion.** "GPT-5.6 Sol's promotional pricing is available at least through November 21, 2026." (pricing page and model page)
  - The model page adds: "a 20% reduction in input pricing and a 33% reduction in output pricing".
  - It does not state the later price. Those ratios would imply $5 / $30, the GPT-5.5 price. That is my inference.
  - At $5 / $30 (and $0.50 cached / $6.25 write), typical QA would be about 266 KRW with caching (331 KRW without), or 75 questions per 20,000 KRW.
- Also quoted: "Cache writes are billed at 1.25x the uncached input token rate." (model page)
- Data-residency endpoints carry "a 10% uplift". This is not included in the model.

## 4. Prompt caching for GPT-5.6 (quoted from https://developers.openai.com/api/docs/guides/prompt-caching.md unless noted)

| Fact | Quote |
|---|---|
| On by default, implicit | "Prompt caching is enabled by default for supported OpenAI models." `prompt_cache_options.mode`: "Defaults to `implicit`." (API reference, responses create .md) |
| Where the implicit write ends | "When `prompt_cache_options.mode` is `implicit`, OpenAI places a breakpoint at the end of the latest eligible message. Eligible messages are: user messages; the last tool response in a consecutive group of tool responses; the last developer message in the initial consecutive group of developer messages." |
| What a write is | "The first request writes an eligible prefix to the cache and subsequent requests look for the longest matching cached prefix available" |
| Minimum length | "The minimum cacheable prompt length is 1,024 tokens for GPT-5.6 and later". Summary table: "1,024 visible input tokens" |
| Prices | "cache writes cost 1.25× the standard, uncached input-token rate … subsequent reads cost only 0.1× that rate." "Cache-write pricing is not an additive fee: input tokens use the uncached-input, cached-input, or cache-write rate." |
| Retention | "The only supported value, `30m`, is also the default. A cached prefix remains eligible for reuse for 30 minutes after its most recent write or reuse, though OpenAI may retain it longer." "reusing the prefix refreshes its lifetime without another cache-write charge." |
| Explicit mode avoids writes | "When no explicit breakpoints are placed, the request does not use prompt caching or create cache writes." "Content after the last selected breakpoint is processed at the uncached input-token rate without a cache-write charge" |
| Shared-prefix gotcha | "caching the first complete request implicitly-only does not make the shorter shared prefix reusable." Remedy: "place an explicit breakpoint after the static content" |
| Usage fields | "Track `usage.input_tokens_details.cached_tokens`, `usage.input_tokens_details.cache_write_tokens`" and ordinary = `input_tokens - cached_tokens - cache_write_tokens` (doc code sample) |
| Routing | "Cached states live on individual machines, where traffic above 15 requests per minute can lead to overflow routing." On GPT-5.6, `prompt_cache_key` "is not needed to optimize caching". |

**What triggers a write charge.**
- Any request in the default implicit mode is charged 1.25× for the tokens between its longest cache hit and its breakpoint (the end of the latest user message or tool output).
- The charge applies whether or not those tokens are ever reused, and it is paid again when a prefix has expired (more than 30 minutes idle).
- Reads refresh the lifetime at no write cost.

**What this means for the tool loop.** Each request resends the whole conversation:
- Request *i* reads request *i−1*'s entire input at 0.1×.
- It writes only the newly appended items (previous reasoning item, function_call, function_call_output) at 1.25×.
- Its output is billed normally.
- The last request's write is wasted: its new tool output is never reused. This costs 0.25× on about 3K tokens, which is cheaper than any uncached alternative.

**Cross-visitor reuse.** The static prefix (tools 419 + developer about 1,204 = about 1,620 tokens, above the 1,024 minimum) is reused only if two conditions hold:
- An explicit breakpoint is placed at the end of the developer message, in an `input_text` block ("Top-level `instructions` cannot contain an explicit breakpoint").
- Another question arrived within 30 minutes.

That saves about 10 KRW per question with sol. It never costs extra, because on a miss the same tokens would be written anyway.

**For one-shot requests (summaries).** Implicit mode writes the whole 70.9K-token input at 1.25×, about +100 KRW with sol, for no reuse. Use `prompt_cache_options: {"mode": "explicit"}` with no breakpoints.

**Reasoning tokens in later requests.**
- "reasoning tokens … are billed as output tokens" (https://developers.openai.com/api/docs/guides/reasoning.md).
- "GPT-5.6 models instead default to rendering available reasoning from earlier turns" (`reasoning.context` = `all_turns`).
- The docs do not say whether re-rendered reasoning counts as billed input tokens on the next request. The model takes a parameter `reasoning_carry` (default 1.0, the conservative case). Carry 0 lowers typical sol cost by about 11 KRW.

## 5. Cost model (`cost_model.py`)

**Per request *i*:**
- input = tools 419 + developer (1,200 + 4) + question 23 (+150 in high) + Σ earlier rounds, where each round = carry × reasoning + args + 23 + tool output.
- output = reasoning + args + 10 formatting tokens for a tool step, or final reasoning + answer + 10 + report_status call 25.

**Cache modes:**
- `none`: explicit mode, no breakpoints.
- `implicit_cold`: the default, nothing warm.
- `implicit_warm`: an explicit breakpoint after the developer message, and that prefix was cached under 30 minutes ago.

### 5.1 Scenarios

| Scenario | Tool steps (payload stat) | Reasoning per tool request / final | Answer | Requests |
|---|---|---|---|---|
| low | search, read_pages(4), read_pages(4) (mean) | 150 / 500 | 500 | 4 |
| typical | search, read_pages(5), read_pages(4) (mean) | 500 / 1,500 | 700 | 4 |
| high | get_toc (max), search (max) ×2, read_pages(5) (p90) ×2; question +150 | 1,500 / 4,000 | 900 | 6 |

### 5.2 Cost per question (KRW) and questions per 20,000 KRW

| Model | Cache | low KRW | low Q/20k | **typical KRW** | **typical Q/20k** | high KRW | high Q/20k |
|---|---|---|---|---|---|---|---|
| gpt-5.6-sol | none | 161 | 124 | 243 | 82 | 727 | 27 |
| gpt-5.6-sol | implicit (cold) | 115 | 174 | **191** | **105** | 534 | 37 |
| gpt-5.6-sol | implicit + warm prefix | 104 | 192 | 181 | 111 | 524 | 38 |
| gpt-5.6-terra | none | 85 | 236 | 132 | 151 | 399 | 50 |
| gpt-5.6-terra | implicit (cold) | 62 | 324 | 106 | 188 | 302 | 66 |
| gpt-5.6-terra | implicit + warm prefix | 57 | 354 | 101 | 198 | 297 | 67 |
| gpt-5.6-luna | none | 8 | 2,357 | 13 | 1,510 | 40 | 501 |
| gpt-5.6-luna | implicit (cold) | 6 | 3,237 | 11 | 1,882 | 30 | 661 |
| gpt-5.6-luna | implicit + warm prefix | 6 | 3,536 | 10 | 1,980 | 30 | 673 |

Typical sol in USD: $0.174 without caching, $0.136 cold, $0.129 warm.

Request trace for typical sol, cold:

| Request | Input | Cached | Written | Output | Cost |
|---|---|---|---|---|---|
| 1 | 1,646 | 0 | 1,646 | 528 | $0.0188 |
| 2 | 4,008 | 1,646 | 2,362 | 545 | $0.0234 |
| 3 | 7,757 | 4,008 | 3,749 | 539 | $0.0311 |
| 4 | 10,820 | 7,757 | 3,063 | 2,235 | $0.0631 |

Output (mostly reasoning) is 56% of the cost in this case. If `report_status` is sent back as a tool output (one more request), add sol +23 KRW, terra +11 KRW, luna +1 KRW.

With the spec's daily cap of 4,000 KRW, typical sol allows about 21 questions per day.

### 5.3 Sensitivity to reasoning tokens (typical loop, KRW per question, cold cache, carry 1.0)

| Reasoning per tool request / final | sol cached | sol no-cache | sol Q/20k | terra cached | luna cached |
|---|---|---|---|---|---|
| 0 / 0 | 96 | 143 | 209 | 50 | 5 |
| 250 / 500 | 136 | 186 | 147 | 74 | 7 |
| 500 / 1,500 | 191 | 243 | 105 | 106 | 11 |
| 1,000 / 3,000 | 286 | 344 | 70 | 162 | 16 |
| 2,000 / 6,000 | 477 | 546 | 42 | 274 | 27 |
| 4,000 / 12,000 | 858 | 949 | 23 | 499 | 50 |

Reasoning volume is the dominant uncertainty: it swings the cost about 9 times.

### 5.4 Summarising the largest chapter once (2023 제3장, 108 pages, 70,914 input tokens, 1 request)

| Model | low (1,500 out + 1,000 reasoning) | typical (3,000 + 3,000) | high (5,000 + 10,000) | Same, if left on the implicit default |
|---|---|---|---|---|
| gpt-5.6-sol | 467 KRW | **565 KRW** | 817 KRW | about +100 KRW each (write premium 0.25 x 70,914 tokens) |
| gpt-5.6-terra | 241 | 300 | 451 | about +49 |
| gpt-5.6-luna | 24 | 30 | 45 | +5 |

Pre-generating all 7 main chapters of 2025 (158,902 input tokens, typical output each, no cache) costs about 2,068 KRW with sol, 1,152 with terra and 115 with luna. This overestimates, because short chapters produce less output.

### 5.5 Spec 4.4 cap check (QA: 10 tool calls, 200K cumulative input)

Worst case: 10 × read_pages(5 pages, max size 3,985 tokens) with heavy reasoning.
- The cumulative input passes 200K on the 9th request, which is forced to be the answer. So **the 200K cap binds before 10 tool calls**.
- Cumulative input 215,712 tokens.
- Cost with sol: **1,692 KRW without caching, 902 KRW with implicit caching**. Terra: 895 / 500. Luna: 89 / 50.
- The largest single request is 46,140 tokens, so there is no long-context pricing.

## 6. Assumptions and uncertainty

**Verified by measurement:**
- Tokenizer (o200k_base on all 3 models; tool-definition rendering was counted on sol only)
- All payload sizes
- Tool-definition size
- Loop input growth (to within 1 token)
- Chapter sizes

**From quoted docs:** prices, the 272K threshold, cache multipliers, the 1,024 minimum, the 30-minute lifetime, the implicit default, and explicit mode with no breakpoints meaning no writes.

**Inferred (not observed; verify on the first real calls through `usage`):**
1. Reasoning tokens per request (150 to 4,000) and the final answer's reasoning (500 to 4,000). The docs only say "a few hundred to tens of thousands". This is the largest uncertainty.
2. `reasoning_carry` = 1.0, meaning earlier reasoning items are billed again as input on later loop requests. Undocumented.
3. Writes are incremental: `cache_write_tokens` = tokens beyond the cached prefix. This follows from the "not an additive fee" wording and the ordinary = input − cached − write formula, but it has not been observed.
4. Cache hits within a question are assumed to be 100%. The docs warn that a shared prefix "doesn't guarantee a cache hit". The no-cache row is the upper bound.
5. Output formatting overhead (10 tokens per item) and the report_status call (25 tokens) are assumptions. The docs confirm hidden formatting tokens exist.
6. Tool outputs use `ensure_ascii=False` compact JSON. With Python's default `json.dumps`, tool-output tokens roughly triple.
7. The developer prompt is set to 1,200 tokens per the task. The measured draft is 1,184.
8. The price of the counting endpoint is undocumented. Its 42 calls are not included in any cost above.
9. Sol's promotional price runs "at least through November 21, 2026". The post-promotion price is not stated.

**Suggested first check in Plan 2 (a few cents).** Run one typical question with sol at the default effort and log `usage` for every request: `input_tokens`, `cached_tokens`, `cache_write_tokens`, `output_tokens`, `reasoning_tokens`. Set `reasoning_tool`, `reasoning_final` and `reasoning_carry` in `cost_model.py` from those numbers, then rerun it.
