# Verification: Plan 3 groundwork, chapter summary + Flex (2026-09-15)

Verifier notes. The repository was not modified (`git status` clean; `assistant/__pycache__` timestamps unchanged).
No OpenAI or Hugging Face calls. Official docs were downloaded as `.md` to a temp folder, grepped, then deleted.

## 한국어 요약 (주석님용)

| 항목 | 검증 결과 |
|---|---|
| 장 크기 표 (44개 장, 2025년치 합계, 가장 큰 장) | **맞음.** 따로 다시 세어 숫자가 모두 똑같이 나왔다 |
| Flex 가격 (sol 절반), 429 무료, 15분 예시, Batch 조건 | **맞음.** 공식 문서에서 다시 확인 |
| 요금 표 | 계산은 **맞음** (±2원). 다만 "추론 토큰 비율 1.78"은 질문 1번에서 잰 값이라 요약에서는 크게 다를 수 있다 |
| 도구 없는 요청 모양 | **맞음** (지금 연결 파일은 `tools: []`를 보낸다). 참고로 OpenAI 공식 Agents SDK는 Responses에 빈 목록을 그대로 보낸다 → 받아 줄 가능성이 높지만, 빼는 방식이 여전히 안전 |
| "근거 대조는 최대 0.55초" | **틀림.** 구절이 틀린 근거 1개당 약 0.03~0.06초. 틀린 근거 54개면 약 3초, 형식이 허용하는 최악(297개)은 약 15초 |
| 새로 찾은 문제 | ① 조수가 "생각 중"을 띄운 뒤 끊기면 다시 시도하지 않는다 ② Flex 혼잡 응답이 "60초 뒤 다시"라고 하면 지금 규칙은 재시도 0번, 503 과부하는 0.5초 만에 재시도 ③ 두 문단에 걸친 구절은 "문단만 확인"이 된다 → 설명서에 한 줄 추가 ④ 방문자가 창을 닫으면 돈만 쓰고 저장이 안 될 수 있다 |
| 바꿀 결정 | 저장본은 매번 대조하지 말고 대조 결과를 저장(대조기·자료가 바뀔 때만 다시) · Flex 재시도 규칙에 503과 Retry-After 반영 · "글자가 나가기 전" 기준을 첫 답 글자로 · 설명서에 "구절은 한 문단 안에서" · 절 개수 확인 · 요약 만들기는 방문자 연결과 분리 |

## 1. Method

- Scratch venv: `summary-verify/.venv` (uv, Python 3.12): openai 3.14.0, httpx2 2.13.0, tiktoken 0.14.0, bm25s 0.3.11.
- Scripts and outputs (this folder):
  - `recount.py` -> `recount_output.json`: independent chapter recount (does not import the researcher's `summary_proto.py`; payload B rebuilt from the report text).
  - `verify_recheck.py` -> `verify_recheck_output.json`, `timing_recheck.py` -> `timing_recheck_output.json`: citation checker on chapter-sized `shown` maps (no white-paper text saved).
  - `wire_recheck.py` -> `wire_recheck_output.json`: MockTransport, dummy key; wire shape, retry/`shown` behaviour, 429 with Retry-After, 503.
  - `cost_recheck_output.txt`: cost table recomputed with an independent formula.
  - Researcher's `progress_proto._self_test()` re-run plus an escaped-quote false-tick test (inline).
  - `wheels/`: `openai-agents 0.22.2` wheel from PyPI, read for how OpenAI's own SDK sends `tools` (sdk-source).
- Docs read (2026-09-15): developers.openai.com `api/docs/pricing.md`, `guides/flex-processing.md`, `guides/batch.md`, `guides/reasoning.md`, `guides/structured-outputs.md`, `guides/prompt-caching.md`, `guides/error-codes.md`, `guides/rate-limits.md`, `guides/background.md`, `guides/streaming-responses.md`, `guides/your-data.md`, `models/gpt-5.6-sol.md`, `api/reference/resources/responses/methods/create.md`.

## 2. Verdicts on the researcher's claims

| # | Claim | Verdict | Evidence (label) |
|---|---|---|---|
| 1 | Flex table: gpt-5.6-sol $2.00/$0.20/$2.50/$10.00 (long $4/$0.40/$5/$15) = half of Standard $4/$0.40/$5/$20 | confirmed | pricing.md "Flex pricing data" and "Standard pricing data" rows (doc) |
| 2 | Batch row equals Flex row | confirmed | pricing.md "Batch pricing data" (doc) |
| 3 | Flex = `service_tier: "flex"`, beta, limited models, Batch rates + caching discounts | confirmed | flex-processing.md: "in beta with limited model availability" (doc) |
| 4 | Capacity shortage = "429 Resource Unavailable", not charged; backoff or retry with `auto`/omitted | confirmed | flex-processing.md "Resource unavailable errors" (doc) |
| 5 | SDK default timeout 10 min, examples 900 s, SDKs retry 408 twice | confirmed | flex-processing.md; SDK `_constants.py` `DEFAULT_TIMEOUT = Timeout(timeout=600, connect=5.0)` (doc, sdk-source) |
| 6 | Project tier restriction -> 400 "Invalid service_tier argument" (default, flex, priority) | confirmed | error-codes.md section "400 - Invalid service_tier argument" (doc) |
| 7 | error.code of the flex 429 is not documented | confirmed | Neither flex-processing.md nor error-codes.md gives a code (doc). The third-party string `resource_unavailable` stays unverified |
| 8 | sol: Batch + streaming + structured outputs; 128K out; 922K in; promo through 2026-11-21 | confirmed | models/gpt-5.6-sol.md (doc) |
| 9 | Batch: 50% off, `24h` only, 50,000 req / 200 MB, `batch_expired`, completed requests billed; Tier 3 queue 100M | confirmed | batch.md lines on limits and expiry; model page rate-limit table (doc) |
| 10 | /v1/batches, /v1/files kept until deleted; purpose=batch files expire after 30 days | confirmed | your-data.md table; SDK `types/file_create_params.py` docstring. Also: batch output file auto-deleted 30 days after completion (batch.md) (doc, sdk-source) |
| 11 | Explicit mode, no breakpoints = no caching, no cache writes; minimum 1,024 for GPT-5.6; writes 1.25x | confirmed | prompt-caching.md "When no explicit breakpoints are placed, the request does not use prompt caching or create cache writes." (doc); SDK `PromptCacheOptions` docstring (sdk-source) |
| 12 | Reserve at least 25,000 tokens; `incomplete` can come before visible output | confirmed | reasoning.md (doc) |
| 13 | Strict subset has minItems/maxItems, pattern, minimum, $defs; 5000 properties / 10 levels; key order kept | confirmed | structured-outputs.md "Supported properties", "Key ordering" (doc). `minimum` is listed under number; on `integer` it is inferred |
| 14 | Reference marks tools/tool_choice optional, silent on an empty array | confirmed | create.md `tool_choice`, `tools` entries (doc). See new finding N4 |
| 15 | SDK: ServiceTier literal incl. flex; tools/tool_choice/service_tier/prompt_cache_options default `omit`; `response.queued`; returned tier may differ | confirmed | `types/responses/service_tier.py`, `resources/responses/responses.py` create signature, `response_queued_event.py`; create.md "This response value may be different" (sdk-source, doc) |
| 16 | Current adapter with tools=[] sends `"tools": []` and `"tool_choice": "none"`; omitting sends neither | confirmed | `wire_recheck_output.json` 1 and 2 (experiment, re-run) |
| 17 | Adapter parses a streamed flex completion; flex 429 -> BUSY, retries ~0.4 s and ~0.9 s | confirmed, with a gap | Re-run: true only without Retry-After. With `retry-after: 60` the policy gives **no retry at all** (`MAX_RETRY_AFTER_S = 20`). 503 `server_is_overloaded` -> SERVER_ERROR, quick retries (experiment) |
| 18 | 44 main chapters; 2025: 248 pp, 225,537 chars, 144,343 (x0.64), 136,919 text tokens, 146,720 payload B | confirmed | `recount_output.json`: identical numbers (experiment) |
| 19 | Largest 2023 제3장 108 pp / 65,946 payload B; median 2023 제2장 31 pp; smallest 2022 제7장 7 pp / 4,475 | confirmed | `recount_output.json` (experiment). Median of 44 is between index 21 (2021 제5장, 18,510) and 22 (2023 제2장, 19,527) |
| 20 | Payload B 0.548-0.601 tokens per payload char; limits.py 1.0/char puts 2023 제3장 at 113,178 > 100K; 2024 제3장 97,547 | confirmed | Recount: same range; request chars 113,178 / 97,547; also 2020 제4장 96,149 (experiment) |
| 21 | No absent printed pages in main chapters; missing.json only 2025 front matter + 부록 1; every citable page has a section; 1-7 sections | confirmed | Recount: 0 gaps, 0 pages without section, section counts equal TOC level-2 counts in all 44; non-citable pages inside chapters are dividers/blanks (at most 166 chars per chapter; 2025 dividers image-only) (experiment) |
| 22 | Token totals A 1,033,561 / B 932,840 / C 923,149 | uncertain | B reproduced exactly; A and C not rebuilt (not decision-relevant) |
| 23a | verify_answer grades a flattened summary (exact, moved paragraph, moved page, paragraph_only, page_not_read, quote_too_short) and regrouping restores sections | confirmed | `verify_recheck_output.json`: 200/200 word-boundary quotes exact; 50/50 moved_page; regroup lengths correct (experiment) |
| 23b | "0.553 s worst case" on 2023 제3장, so re-verify on every display is free | **refuted** | Each citation whose quote is absent scans every paragraph of the chapter: 0.03-0.06 s each here. 25 absent: 0.81-1.28 s; 54 absent: 2.7-3.4 s; schema maximum (12x8+3 sentences x 3 citations = 297): 14.6 s (experiment; HF CPU Basic likely slower, inferred) |
| 24 | One output sentence with 1-2 citations ~120 tokens | uncertain | Not re-run; arithmetic plausible (Korean ~0.61-0.65 tokens/char) |
| 25 | Live check final turn 447 output / 286 reasoning / 161 visible = 1.78 | confirmed | docs/research/2026-09-15-first-live-check.md question 1, request 3 (experiment record). Note it is one QA turn with 4.8K input |
| 26 | Cost table (typical 273/136, largest 640/320, 2025 1,946/973, 44 chapters 12,267/6,134, ceiling 1,270/635, 73/147 per 20,000 KRW) | confirmed (arithmetic only) | `cost_recheck_output.txt` matches within 2 KRW. The reasoning scenarios themselves are unmeasured (inferred) |
| 27 | Implicit cache premium +94 / +29 / +214 / +1,360 KRW | confirmed (arithmetic) | 0.25 x input x $4 x 1,400 (doc multiplier) |
| 28 | Progress regex emits 6 sections in order + overview under random chunking | confirmed | Self-test re-run OK (experiment) |
| 29 | Progress regex can false-tick on a literal `"title":` inside a quote | refuted | In valid JSON inner quotes are escaped (`\"title\":`), so the pattern cannot match; test with such text gave exactly 1 section + 1 overview (experiment) |
| 30 | output_text streams as `response.output_text.delta`; adapter ignores it | confirmed | SDK `response_text_delta_event.py`; `assistant/llm_openai.py` (sdk-source) |
| 31 | Third-party: empty tools array -> 400 | uncertain | Portkey page quotes "Invalid 'tools': expected an array with at least one element" but names no endpoint; OpenAI's own Agents SDK sends `tools=[]` on the Responses path (N4) |
| 32 | Spec 4.4 summary caps are 100K input / 16K output (30K is QA) | confirmed | spec 4.4 table; `limits.py` QA_CAPS output 30,000 (doc) |
| 33 | "180 s adapter timeout is too short" for summaries | uncertain | With stream=True the SDK timeout is an httpx per-read (inactivity) timeout, also sent as `x-stainless-read-timeout` (`_base_client.py`). It trips only if no byte arrives for 180 s. Raising it is harmless; whether silence that long happens is unknown (sdk-source, inferred) |
| 34 | Docs are silent on streaming with flex | confirmed | flex-processing.md and streaming-responses.md have no statement (doc) |
| 35 | Groundwork's 70,914 used a different payload shape | confirmed | token-costs/token_costs.md: [developer(summary prompt 163), user(payload)] (doc record) |

## 3. New findings

- **N1 Verification cost is per absent quote, not fixed.** `check_citation` recomputes `keyed()` for every candidate paragraph (the whole chapter for a quote that is nowhere). 2023 제3장: 0.03-0.06 s per absent citation, 2.7-3.4 s for 54, 14.6 s for the schema maximum of 297 (experiment). "Re-verify on every display" blocks a CPU Basic worker for seconds on bad summaries.
- **N2 `thinking` already counts as shown.** In `llm_openai.py` every `emit` sets `shown=True`, including `thinking` (reasoning item added). Re-run: an `error` event after the reasoning item -> `stream_broken`, one request, no retry. For summaries with long silent reasoning, a transient failure before any answer text is never retried (experiment). The spec rule is about letters on screen (spec 4.3).
- **N3 Flex retry gaps.** A 429 carrying `Retry-After` above 20 s gets no retry; a 503 `server_is_overloaded` is retried after ~0.5 s and ~1 s (experiment). rate-limits.md: overload is 503 `server_is_overloaded`, "Handle both 429 and 503" (doc). A pre-generation policy must cover both and honour Retry-After.
- **N4 Empty tools array is probably accepted by Responses.** `openai-agents 0.22.2` `models/openai_responses.py` passes `converted_tools_payload` even when empty (omits only with prompt templates), while its Chat Completions path omits an empty list (sdk-source). The Portkey 400 page names no endpoint. The recommended "omit both keys" stays correct and costs nothing.
- **N5 Quotes spanning two numbered paragraphs fail.** 50/50 such quotes graded `paragraph_only/quote_not_in_paragraph` (experiment). In main chapters about 55% of numbered "paragraphs" are shorter than 30 chars (headings, list and table lines; median 21-25 chars, p75 134-155) (experiment). The prompt draft does not say a quote must stay inside one numbered paragraph.
- **N6 Section count is not enforced.** Schema allows 1-12 sections with free titles; the model can merge, skip or rename sections and the regroup still "works". Nothing compares output sections with input sections. A per-chapter schema could fix the count (`minItems = maxItems = N`, supported) but each new schema adds first-request latency (structured-outputs.md) (doc, inferred).
- **N7 Visitor disconnect can waste a paid summary.** If Gradio cancels the event generator when the visitor leaves (behaviour varies by version; gradio issues #8503, #6239, PR #10827), the stream closes; for a synchronous response "To cancel a synchronous response, terminate the connection" (background.md). Tokens already generated are presumably billed and nothing is saved (inferred). Generation should run in a worker detached from the visitor event.
- **N8 Background mode is an unconsidered option.** `background=true` + `stream=true` allows resuming a dropped stream with `starting_after` and cancelling; `store=false` is allowed but data is stored temporarily (~10 minutes); time to first token is higher (background.md, doc). Flex compatibility is not documented. Not needed for the demo, but it is the documented tool for long requests that may lose the connection.
- **N9 Storage key mismatch.** The report says `summaries/{year}/ch{NN}/{prompt_version}/{model}.json` with `corpus_hash` in the record; `summary_proto.storage_key()` puts `{corpus_hash[:12]}.json` in the path. With the hash in the path a stale summary is never found (no "stale" state). Use the report's form.
- **N10 Spec 4.4 cost column must change with 32K.** At the 100K input cap and 32K output one summary can cost 1,456 KRW (1,008 at 16K); largest real chapter 1,270 KRW. Any pre-send reservation against the 4,000 KRW daily stop should use these (experiment arithmetic).
- **N11 `on_text` must follow only the final-answer message.** gpt-5.6 message items carry `phase`; the adapter already skips `commentary`. Deltas should be filtered by the `item_id` of a non-commentary message, or a commentary message would feed the progress parser (inferred; live check saw no commentary).
- **N12 "Flex is not available for this model."** appears in a June 2026 community thread (third-party client context) as the message for an unsupported model; sol is in the Flex table, so this matters only if the model changes (community, low confidence).

## 4. Corrected decisions

1. **Saved summaries: store the verified answer, re-verify only on change.** Keep `answer_raw` and the verified answer; add a checker fingerprint (hash of `assistant/citations.py` + `assistant/textnorm.py`) next to `corpus_hash`, and re-verify only when either differs (or memoize `keyed()` per paragraph). Why: N1, claim 23b refuted.
2. **Flex pre-generation retry policy:** treat any 429 without a billing code and 503 `server_is_overloaded` the same; wait `max(Retry-After, 30/60/120/240 s)`; never retry billing codes or 400 invalid `service_tier` (resend standard only with `--fallback-standard`). Why: N3.
3. **Summary "shown" = first answer text delta.** `queued`, `thinking` and `answer_started` are progress lines, not answer text, so the two quick retries stay available until the first `response.output_text.delta` of the final-answer message. Why: N2, spec 4.3 wording.
4. **Prompt draft: add one rule.** "quote는 번호 붙은 문단 하나 안에서만 고른다. 두 문단(줄)에 걸친 구절은 쓰지 않는다." Why: N5.
5. **Check sections after the answer.** Compare output section count and titles with the input; flag mismatches in the pre-generation CLI (and do not save a visitor summary that drops sections, or show it with a notice). Why: N6.
6. **Run first-time summary generation detached from the visitor's event** (worker + per-key lock), stream progress to whoever is watching, save on completion. Why: N7 (inferred).
