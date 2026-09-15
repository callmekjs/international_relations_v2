# Live run log — gpt-5.6-sol agent loop (sanitised)

Date: 2026-09-15 · SDK `openai` 3.14.0 · Responses API · `store=False` · `stream=True` · `reasoning.effort="low"` · SDK retries off (`max_retries=0`) so the call count is exact.
Key: read from `C:\international_relations\.env` inside the process. Never printed or written. `grep "sk-"` over every output file found 0 matches.
Raw records: `live_run_raw.json`, `probes_extra_raw.json`, console logs `live_console.txt`, `probes_console.txt`.
Prices used (USD per 1M tokens, Standard, short context): input 4.00 · cached 0.40 · cache write 5.00 · output 20.00.

## Non-generation checks (not counted as model calls)
- `models.retrieve("gpt-5.6-sol")` → `id=gpt-5.6-sol`, `owned_by=system`.
- `responses.input_tokens.count` for call 1's payload (instructions + 2 tools + question) → **592**, the same as call 1's reported `input_tokens`.
- `--dry-run` (no network): SDK-typed events built with `openai._models.construct_type` drove the real loop and the real corpus worker. Checked: year filter (a 2021 page was refused), citation mapping, unknown-ID detection.

## Model calls (6 of 6 allowed)

| # | Purpose | model (response) | status | input | cached | cache_write | output | reasoning | max_output_tokens | cost USD |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | loop: plan → `search` | gpt-5.6-sol | completed | 592 | 0 | 0 | 44 | 10 | 2000 | 0.003248 |
| 2 | loop: `read_pages` | gpt-5.6-sol | completed | 1,613 | 0 | 1,610 | 82 | 44 | 2000 | 0.009702 |
| 3 | loop: final answer | gpt-5.6-sol | completed | 4,049 | 1,610 | 2,436 | 84 | 0 | 2000 | 0.014516 |
| 4 | probe: tools + `text.format` json_schema (strict) | gpt-5.6-sol | completed | 4,254 | 0 | 4,251 | 131 | 52 | 2000 | 0.023887 |
| 5 | probe A: `max_output_tokens=16` | gpt-5.6-sol | **incomplete** (`reason=max_output_tokens`) | 592 | 0 | 0 | 16 | 16 | 16 | 0.002688 |
| 6 | probe B: two-year question (parallel calls?) | gpt-5.6-sol | completed | 595 | 0 | 0 | 95 | 21 | 2000 | 0.004280 |
| | **Total** | | | 11,695 | 1,610 | 8,297 | 452 | 143 | | **0.058321** (≈ 82 KRW at 1,400) |

Loop alone (calls 1–3, one full question): **$0.027466** (≈ 38 KRW).

## Loop trace (question "2023년 한미 정상회담은 어디서 열렸어?", years=[2023])
1. Call 1 → reasoning item (encrypted 1,252 chars) + `search {"query":"한미 정상회담 개최 장소","years":[2023],"k":5}` → tool output 1,725 chars (JSON hits).
2. Call 2 (input: user, reasoning, function_call, function_call_output) → reasoning (1,484 chars) + `read_pages {"page_ids":["2023-p027R","2023-p180L","2023-p187R"]}` → tool output 3,502 chars (3 citation-marked page blocks).
3. Call 3 (7 input items) → one `message`, `phase=final_answer`, no reasoning tokens:
   > 2023년 한미 정상회담은 두 차례 열렸습니다.
   > - **4월 26일:** 미국 **워싱턴 D.C.** [1]
   > - **8월 18일:** 미국 **캠프 데이비드** [2]
   >
   > [1] 2023년치 · 「2023년도 국제정세와 외교활동」 358쪽 (2023-p180L) · [2] 같은 판 373쪽 (2023-p187R)
   - Raw markers `\ue200cite\ue202turn1file1\ue201` and `…turn1file2…`: both valid, no invented IDs. The model read 3 pages and cited 2.
   - It matches the corpus. p019L also says "두 차례 한·미 정상회담(4.26, 8.18)".
4. Every response reported `reasoning = {context: all_turns, effort: low, mode: standard}` and `tools[*].strict = [true, true]`.

## Observed stream event names

| Call | Event order (consecutive repeats merged) · counts |
|---|---|
| 1, 2 (tool call) | `response.created` → `response.in_progress` → `response.output_item.added` (reasoning) → `response.output_item.done` → `response.output_item.added` (function_call) → `response.function_call_arguments.delta` ×20 / ×23 → `response.function_call_arguments.done` → `response.output_item.done` → `response.completed` |
| 3 (answer) | `response.created` → `response.in_progress` → `response.output_item.added` (message) → `response.content_part.added` → `response.output_text.delta` ×67 → `response.output_text.done` → `response.content_part.done` → `response.output_item.done` → `response.completed` |
| 4 (json_schema) | as call 3, with a reasoning `output_item.added/done` pair first; output_text ×67 deltas |
| 5 (incomplete) | `response.created` → `response.in_progress` → `response.output_item.added` (reasoning) → `response.output_item.done` → **`response.incomplete`** (it carries `usage`) |
| 6 (parallel) | reasoning added/done, then twice: `output_item.added` (function_call) → `function_call_arguments.delta` ×1 → `function_call_arguments.done` → `output_item.done`; then `response.completed` |

Never seen: `error`, `response.failed`, `response.refusal.*`, `response.reasoning_summary_*` (summary not requested), `response.output_text.annotation.added`.
Time to first event 0.8–2.1 s; each call 2.1–3.5 s end to end.

## Findings from the calls
- **Stateless replay works.** Reasoning items were replayed as `item.to_dict()` together with function_call and function_call_output items, and 2 continuations accepted them. Call 3 read 1,610 cached tokens, so the replayed prefix rendered the same as in call 2.
- **Terminal event vs `output_item.done`:** the reasoning `encrypted_content` in `response.output_item.done` differed from the copy in the terminal event's `response.output` in all 5 cases. The terminal copy was the one replayed, and it was accepted.
- **Caching:** call 1 (592 tokens, under the 1,024 minimum) wrote nothing. Implicit mode then wrote nearly the whole input each call (1.25×) and read it back on the next call (0.1×). The probe (same history plus `text.format` plus a new user turn) got **0 cached** and re-wrote 4,251 tokens.
- **Structured output with tools attached:** accepted, and the JSON was valid for the strict schema: `{"meetings":[{"date":"2023-04-26","place":"워싱턴 D.C.","page_ids":["2023-p180L"]},{"date":"2023-08-18","place":"캠프 데이비드","page_ids":["2023-p027R","2023-p187R"]}]}`. No tool was called in that response. No refusal.
- **Incomplete path:** `status=incomplete`, `incomplete_details.reason=max_output_tokens`, only a reasoning item, `output_text=""`. Tokens were still billed (16 output).
- **Parallel calls:** one response held 2 `function_call` items (years 2022 and 2025), and `parallel_tool_calls` came back `true`.
- No worker processes were left running (the corpus worker ran as a context-managed subprocess of the project venv with `PYTHONDONTWRITEBYTECODE=1`). No files in `C:\international_relations` changed.
