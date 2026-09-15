# OpenAI agent loop for gpt-5.6-sol — facts and recommended design (Plan 2 groundwork)

Checked 2026-09-15. SDK: `openai` 3.14.0 (latest on PyPI at install time; it uses `httpx2`).
Docs were read from the official Markdown copies (`<page>.md`, advertised in https://developers.openai.com/api/docs/llms.txt).
Local copies are in `docs/` in this folder. URLs below are the canonical pages. Every page was readable; none needed JavaScript.

Legend: **V-doc** = quoted from docs · **V-sdk** = read in SDK source · **V-live** = seen in a live call (see `live_run_log.md`) · **I** = inferred

## 1. API choice

| # | Claim | Quote (exact) | Source | Kind |
|---|---|---|---|---|
| 1.1 | Responses is the recommended API for new work | "While Chat Completions remains supported, Responses is recommended for all new projects." | https://developers.openai.com/api/docs/guides/migrate-to-responses | V-doc |
| 1.2 | Same advice in the deployment checklist | "**Always start** with the [Responses API]" | https://developers.openai.com/api/docs/guides/deployment-checklist | V-doc |
| 1.3 | Chat Completions cannot combine tools with reasoning | "Starting with GPT-5.4, Chat Completions does not support tool calling with `reasoning_effort` values other than `none`." | migrate-to-responses (above) | V-doc |
| 1.4 | Same rule, stated for GPT-5.6 | "For GPT-5.6, function tools in Chat Completions are compatible only with effective reasoning `none`. Reasoning with tools should use the Responses API." | https://developers.openai.com/api/docs/guides/upgrading-to-gpt-5p6-sol | V-doc |
| 1.5 | **Decision: Responses API.** Chat Completions is not an option for a reasoning tool loop on this model. | — | 1.1–1.4 | I (forced by 1.3/1.4) |

## 2. Function tools, calls, outputs

| # | Claim | Quote (exact) | Source | Kind |
|---|---|---|---|---|
| 2.1 | Tool fields: `type`, `name`, `description`, `parameters` (JSON Schema), `strict` | table: "`type` This should always be `function`", "`parameters` JSON schema defining the function's input arguments", "`strict` Whether to enforce strict mode for the function call" | https://developers.openai.com/api/docs/guides/function-calling | V-doc |
| 2.2 | Strict mode needs two things | "1. `additionalProperties` must be set to `false` for each object in the `parameters`. 1. All fields in `properties` must be marked as `required`." | function-calling | V-doc |
| 2.3 | Optional fields use a nullable type | "You can denote optional fields by adding `null` as a `type` option" | function-calling | V-doc |
| 2.4 | In Responses, leaving out `strict` makes the API try strict first | "Responses requests will attempt to normalize your schema into strict mode when possible, and will fall back to non-strict, best-effort function calling if the schema cannot be made compatible with strict mode. When fallback happens, the response tool will show `strict: false`." | function-calling | V-doc |
| 2.5 | Our schemas (`["array","null"]`, `["integer","null"]`, `minItems`/`maxItems`) were accepted as strict; `response.tools[*].strict` came back `true` | — | live call 1–3 | V-live |
| 2.6 | Strict schema subset = Structured Outputs subset (see section 5) | "Some features of JSON schema are not supported. (See [supported schemas]…)" | function-calling | V-doc |
| 2.7 | A call comes back as a `function_call` output item | "Each entry with a `call_id` (used later to submit the function result), `name`, and JSON-encoded `arguments`." | function-calling | V-doc |
| 2.8 | One response can hold several calls | "The model may choose to call multiple functions in a single turn. You can prevent this by setting `parallel_tool_calls` to `false`, which ensures exactly zero or one tool is called." | function-calling | V-doc |
| 2.9 | Two `search` calls came back in one response when asked about two years (`parallel_tool_calls` came back `true`) | — | extra probe B | V-live |
| 2.10 | Return each result as a `function_call_output` with the same `call_id`; output is usually a string | "The result you pass in the `function_call_output` message should typically be a string, where the format is up to you (JSON, error codes, plain text, etc.)." | function-calling | V-doc |
| 2.11 | SDK input type: `{"type":"function_call_output","call_id":…, "output": str \| list}` | `output: Required[Union[str, ResponseFunctionCallOutputItemListParam]]` | `openai/types/responses/response_input_item_param.py` | V-sdk |
| 2.12 | Tool definitions cost input tokens | "callable function definitions count against the model's context limit and are billed as input tokens." | function-calling | V-doc |
| 2.13 | `max_tool_calls` does **not** limit our own functions, so the 10-call cap must live in our loop | "The maximum number of total calls to built-in tools that can be processed in a response." | https://developers.openai.com/api/reference/resources/responses/methods/create | V-doc |
| 2.14 | `tool_choice` options | "`tool_choice: "auto"`" (default), "`tool_choice: "required"`", "`tool_choice: {"type": "function", "name": "get_weather"}`", `allowed_tools` with `mode` `auto`/`required`, and "You can also set `tool_choice` to `"none"`" | function-calling; create reference | V-doc |
| 2.15 | `allowed_tools` exists so the `tools` list can stay the same for caching | "…but not modify the list of tools you pass in, so you can maximize savings from [prompt caching]" | function-calling | V-doc |

## 3. Reasoning items and conversation state

| # | Claim | Quote (exact) | Source | Kind |
|---|---|---|---|---|
| 3.1 | Reasoning items must be sent back together with tool outputs | "any reasoning items returned in model responses with tool calls must also be passed back with tool call outputs." | function-calling | V-doc |
| 3.2 | …and everything since the last user message | "If the model calls multiple functions consecutively, you should pass back all reasoning items, function call items, and function call output items, since the last `user` message." | https://developers.openai.com/api/docs/guides/reasoning | V-doc |
| 3.3 | Stateless mode returns encrypted reasoning without any `include` setting | "When you create a response in stateless mode, reasoning items in the response's `output` array include an `encrypted_content` property by default. Stateless mode applies when `store` is `false`…" | reasoning | V-doc |
| 3.4 | Seen live with `store=False`: every reasoning item had `encrypted_content` (1,252–1,528 chars). Sending it back was accepted on calls 2, 3 and the probe. | — | live | V-live |
| 3.5 | GPT-5.6 default `reasoning.context` is `all_turns`; check the value on the response | "Omit `reasoning.context` or set it to `auto` to use `all_turns`, the GPT-5.6 default. Check the response's `reasoning.context` field to confirm the effective mode." | https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6 | V-doc |
| 3.6 | Every live response reported `reasoning = {context: all_turns, effort: low, mode: standard}` | — | live | V-live |
| 3.7 | Manual replay must keep every output item | "When managing history manually, preserve and resend previous user inputs and every response output item. For `store: false` or Zero Data Retention, replay the encrypted reasoning items that the API returns by default." | latest-model/gpt-5.6 | V-doc |
| 3.8 | `previous_response_id` does not reduce cost | "Even when using `previous_response_id`, all previous input tokens for responses in the chain are billed as input tokens in the API." | https://developers.openai.com/api/docs/guides/conversation-state | V-doc |
| 3.9 | `store` is true by default and keeps data for 30+ days | "Defaults to true when omitted. If set to true, response data will be stored for at least 30 days" | create reference | V-doc |
| 3.10 | Abuse-monitoring logs apply either way | "By default, abuse monitoring logs are generated for all API feature usage and retained for up to 30 days" | https://developers.openai.com/api/docs/guides/your-data | V-doc |
| 3.11 | Assistant `phase` must survive replay | "when sending follow-up requests, preserve and resend phase on all assistant messages — dropping it can degrade performance." | `openai/types/responses/response_output_message.py` | V-sdk |
| 3.12 | Final messages came back with `phase: "final_answer"`; no `commentary` messages appeared in these runs | — | live | V-live |
| 3.13 | **Replay with `item.to_dict()`, not `item.model_dump()`.** On pydantic v2, `model_dump()` emits the Python name `async_` (with `None`). `to_dict()` uses API field names and leaves out unset fields. The API's reaction to `async_` was not tested. | SDK `to_dict`: "keys will match the API response, *not* the property names from the model." | `openai/_models.py`; local run | V-sdk (+ untested API side) |
| 3.14 | When streaming, the SDK says to reuse reasoning from `output_item.done`, not `output_item.added` | "When streaming, use the completed reasoning item and its `encrypted_content` from the `response.output_item.done` event in subsequent requests. The `encrypted_content` in `response.output_item.added` may be incomplete." | `openai/types/responses/response_reasoning_item.py` | V-sdk |
| 3.15 | Live: `encrypted_content` from `output_item.done` was **not byte-identical** to the copy in the terminal event's `response.output`. We replayed the terminal-event copy and it was accepted. | — | live, all 5 reasoning items | V-live (meaning unknown) |

## 4. Model parameters (gpt-5.6-sol)

| # | Claim | Quote (exact) | Source | Kind |
|---|---|---|---|---|
| 4.1 | Context and output limits | "1,050,000 context window" · "Maximum input tokens: 922,000" · "128,000 max output tokens" · "Feb 16, 2026 knowledge cutoff" | https://developers.openai.com/api/docs/models/gpt-5.6-sol | V-doc |
| 4.2 | Effort values and default (note: no `minimal`) | "Reasoning.effort supports: none, low, medium (default), high, xhigh, and max." | models/gpt-5.6-sol | V-doc |
| 4.3 | `low` fits tool and search work | "`low` … Ideal for use cases requiring tool-use, planning, search, or multi-step decision making, while optimizing for speed and cost." | reasoning | V-doc |
| 4.4 | `reasoning.mode`: `standard` (default) or `pro` | "`standard` is the default. Set `reasoning.mode` to `pro` for difficult tasks…" | reasoning | V-doc |
| 4.5 | Verbosity knob | "Currently supported values are `low`, `medium`, and `high`. The default is `medium`." (`text.verbosity`) | create reference | V-doc |
| 4.6 | `max_output_tokens` includes reasoning tokens | "An upper bound for the number of tokens that can be generated for a response, including visible output tokens and [reasoning tokens]" | create reference | V-doc |
| 4.7 | Running out gives `incomplete` status, possibly with no visible text | "you'll receive a response with a `status` of `incomplete` and `incomplete_details` with `reason` set to `max_output_tokens`. This might occur before any visible output tokens are produced" | reasoning | V-doc |
| 4.8 | Live with `max_output_tokens=16`: `status=incomplete`, `reason=max_output_tokens`, only a reasoning item, empty `output_text`, `usage` present (592 in / 16 out / 16 reasoning), terminal event `response.incomplete` | — | extra probe A | V-live |
| 4.9 | Starting buffer OpenAI suggests while experimenting | "OpenAI recommends reserving at least 25,000 tokens for reasoning and outputs when you start experimenting with these models." | reasoning | V-doc |
| 4.10 | Price per 1M (Standard, short context): input $4.00, cached $0.40, **cache writes $5.00**, output $20.00. Above 272K input: $8 / $0.80 / $10 / $30. | "Cache writes are billed at 1.25x the uncached input token rate." · "Prompts with >272K input tokens are priced at 2x input and 1.5x output for the full request." | https://developers.openai.com/api/docs/pricing ; models/gpt-5.6-sol | V-doc |
| 4.11 | Tier 1 rate limit for this model: 500 RPM, 500,000 TPM | rate-limit table on the model page | models/gpt-5.6-sol | V-doc |
| 4.12 | Safeguards can refuse or pause a stream | "safeguards that block or refuse some requests due to real-time cyber and biology misuse classifiers … generation is paused for several seconds mid-stream" | latest-model/gpt-5.6 | V-doc |
| 4.13 | Send a per-user `safety_identifier` | "If your application serves individual end users, send a stable, privacy-preserving `safety_identifier` with each request." | latest-model/gpt-5.6 | V-doc (the parameter was accepted live) |

## 5. Structured outputs (for table and compare)

| # | Claim | Quote (exact) | Source | Kind |
|---|---|---|---|---|
| 5.1 | Request shape | "`text: { format: { type: "json_schema", "strict": true, "schema": ... } }`" (`name` is required: "Must be a-z, A-Z, 0-9, or contain underscores and dashes, with a maximum length of 64.") | https://developers.openai.com/api/docs/guides/structured-outputs ; create reference | V-doc |
| 5.2 | Size limits | "A schema may have up to 5000 object properties total, with up to 10 levels of nesting." · "…total string length of all property names, definition names, enum values, and const values cannot exceed 120,000 characters." · "A schema may have up to 1000 enum values across all enum properties." | structured-outputs | V-doc |
| 5.3 | Shape rules | "Root objects must not be `anyOf` and must be an object" · all fields `required` · "`additionalProperties: false` must always be set in objects" · "outputs will be produced in the same order as the ordering of keys in the schema" | structured-outputs | V-doc |
| 5.4 | Supported types and keywords | types: String, Number, Boolean, Integer, Object, Array, Enum, anyOf; string `pattern`, `format` (date-time, time, date, duration, email, hostname, ipv4, ipv6, uuid); number `multipleOf`, `maximum`, `exclusiveMaximum`, `minimum`, `exclusiveMinimum`; array `minItems`, `maxItems`; `$defs` and recursion supported | structured-outputs | V-doc |
| 5.5 | Not supported | "**Composition:** `allOf`, `not`, `dependentRequired`, `dependentSchemas`, `if`, `then`, `else`" | structured-outputs | V-doc |
| 5.6 | How a refusal looks | "the API response will include a new field called `refusal`"; example output content `{"type": "refusal", "refusal": "I'm sorry, I cannot assist with that request."}`; stream events `response.refusal.delta` / `response.refusal.done` | structured-outputs; streaming-events reference | V-doc |
| 5.7 | `text.format` together with function tools **in one request**: the docs never say it outright. The SDK `responses.parse()` / `stream()` accept both `text_format` and `tools`, and parse both `function_call` and `output_text` from one response. | — | `openai/lib/_parsing/_responses.py` | V-sdk |
| 5.8 | Live: a request with both tools and a strict `json_schema` format completed and returned schema-valid JSON (2 meetings, with page_ids). The model chose not to call a tool, so "tool call and JSON answer in the same run with this format" is still untested. | — | live probe | V-live (partial) |
| 5.9 | Changing `text.format` changes the cached prefix | table row "`text.format` … Adds output-format instructions and the requested schema." | https://developers.openai.com/api/docs/guides/prompt-caching | V-doc |
| 5.10 | Live: the probe reused call 3's prefix but set `text.format` → `cached_tokens` was 0 and `cache_write_tokens` was 4,251. Either the format change or the new user turn could have caused it; one call cannot tell which. | — | live probe | V-live / cause I |

## 6. Streaming events (names from SDK union and streaming reference; ✓ = seen live)

| UI step | Event | Payload used | Live |
|---|---|---|---|
| request accepted | `response.created`, `response.in_progress` | `response.id` | ✓ |
| thinking started | `response.output_item.added` with `item.type == "reasoning"` | — | ✓ |
| tool call started | `response.output_item.added` with `item.type == "function_call"` | `item.name`, `item.call_id` (arguments are `""`) | ✓ |
| arguments streaming | `response.function_call_arguments.delta` | `delta`, `item_id`, `output_index` | ✓ (1–23 deltas per call) |
| arguments final | `response.function_call_arguments.done` | `arguments` (full JSON string), `item_id` | ✓ |
| item finished | `response.output_item.done` | full `item` (function_call / reasoning / message) | ✓ |
| answer text | `response.content_part.added` → `response.output_text.delta` … → `response.output_text.done` → `response.content_part.done` | `delta` | ✓ |
| refusal text | `response.refusal.delta` / `.done` | `delta` | not seen |
| finished with usage | `response.completed` / `response.incomplete` / `response.failed` | `response` (with `usage`, `status`, `incomplete_details`, `output`) | completed ✓, incomplete ✓ |
| stream error | `error` | `code`, `message` | not seen |
| reasoning summary (only if `reasoning.summary` is set) | `response.reasoning_summary_part.added/done`, `response.reasoning_summary_text.delta/done` | — | not requested |

- Doc quote: "Streaming can be used to surface progress by showing which function is called as the model fills its arguments, and even displaying the arguments in real time." (function-calling) V-doc
- **SDK trap (V-sdk):** `ResponseStream.get_final_response()` raises `RuntimeError("Didn't receive a `response.completed` event.")` when the run ends `incomplete` or `failed`. Our loop should read the terminal response straight from `response.completed | response.incomplete | response.failed`. The SDK itself rebuilds `output` from `output_item.done` items when the terminal event has no `output` (comment: "Recover finalized items"), and our loop does the same.
- Usage is only on the terminal event's `response.usage`. Delta events carry none (V-sdk types + V-live).

## 7. Usage accounting

| Field | Meaning | Source |
|---|---|---|
| `usage.input_tokens` | all input tokens, **including** cached and cache-write tokens | V-doc (formula below) |
| `usage.input_tokens_details.cached_tokens` | read from cache (0.1× rate) | create reference; V-live |
| `usage.input_tokens_details.cache_write_tokens` | "The number of input tokens that were written to the cache." (1.25× rate) | create reference; V-sdk `ResponseUsage`; V-live |
| `usage.output_tokens` | all generated tokens, including reasoning and hidden formatting tokens | token-counting guide: "Reported output token usage includes all tokens generated by the model, not only the text visible in a response." |
| `usage.output_tokens_details.reasoning_tokens` | reasoning part of `output_tokens` (already included in it) | reasoning guide |
| `usage.total_tokens` | input + output | — |

Cost per call, from the docs' own formula: `ordinary = input − cached − cache_write` → `$ = (ordinary×4.00 + cached×0.40 + cache_write×5.00 + output×20.00) / 1e6` (use the long-context row above 272K).
Quote: "`ordinary_input_tokens = input_tokens - cached_tokens - cache_write_tokens`" (https://developers.openai.com/api/docs/guides/prompt-caching). V-doc.
Caching facts: "The minimum cacheable prompt length is 1,024 tokens for GPT-5.6 and later". With implicit mode, "OpenAI places a breakpoint at the end of the latest eligible message", which includes "the last tool response in a consecutive group of tool responses". Live: call 1 (592 tokens) wrote nothing; call 2 wrote 1,610; call 3 read 1,610 and wrote 2,436.

Free pre-flight: `client.responses.input_tokens.count(...)` takes the same payload and returns `input_tokens`. It generates nothing. Live: 592 tokens for instructions + 2 tools + question, the same number call 1 reported.

## 8. Errors and retries

- SDK default `DEFAULT_MAX_RETRIES = 2`. `_should_retry` retries 408, 409, 429 and ≥500, and obeys `x-should-retry` (V-sdk `_constants.py`, `_base_client.py`).
- 429 also covers spend and credit limits: `project_spend_limit_exceeded`, `organization_spend_limit_exceeded`, `credit_balance_exhausted`. "Retrying billing, spend, or quota errors won't restore API access." (https://developers.openai.com/api/docs/guides/error-codes) V-doc. So: catch `openai.RateLimitError`, read `.code`, and show "이번 달 사용량이 다 찼어요" for those codes (it is I whether the server sends `x-should-retry: false` for them).
- A project-level spend limit is OpenAI's counterpart to the spec's "Anthropic workspace $14 limit" (I, from the error codes above; how to set it in the dashboard was not checked).

---

## 9. Recommended loop design (to replace spec §3.2, §4.3, §4.4 wording)

**Endpoint and mode**
1. `client.responses.create(stream=True, store=False, ...)`, stateless with full manual replay. Why:
   - visitor questions are not kept as 30-day application state (3.9);
   - it costs the same as `previous_response_id` (3.8);
   - our run log needs every item anyway (for replaying 예시 모음);
   - it does not depend on server-side state lookups.
   Leave `include` out; encrypted reasoning arrives by default (3.3, 3.4).
2. Leave `reasoning.context` out (effective `all_turns`, 3.6). Each run is one question, so current-turn and all-turns behave alike inside it.

**Per request (initial values)**
```python
client.responses.create(
    model="gpt-5.6-sol",
    instructions=TASK_PROMPT,          # stable text → implicit cache prefix
    input=history,                     # user msg + every output item (to_dict) + function_call_output items
    tools=TOOLS,                       # identical list every call (cache); strict=True, nullable optionals
    tool_choice="auto",               # "none" on the last allowed call (tool cap / token cap reached)
    reasoning={"effort": "low"},      # start low (live: correct answer, ≤52 reasoning tokens/call); compare medium on gold set
    max_output_tokens=8000,            # per call; ~$0.16 worst case output; tune after gold run
    store=False, stream=True,
    safety_identifier=hashed_visitor_id,
    # text={"format": {...json_schema...}}  # table/compare only — set on EVERY call of that run
)
```
Client: `OpenAI(max_retries=2, timeout=...)`, but never retry the spend and credit 429 codes.

**Loop**
```
history = [user message]
for call in 1..MAX_CALLS:
    stream events → on_event (map in §6); keep output_item.done items as a fallback
    resp = terminal event's response (completed | incomplete | failed)   # not get_final_response()
    record usage row + cost (§7)
    history += [item.to_dict() for item in resp.output]                   # reasoning, function_call, message(phase)
    if resp.status == "incomplete": stop → show "충분히 찾지 못했어요" (reason in incomplete_details)
    if resp.status == "failed": stop → error message
    calls = [i for i in resp.output if i.type == "function_call"]         # may be >1 (parallel)
    if not calls: final answer = resp.output_text (message with phase final_answer); break
    for c in calls: history.append({"type":"function_call_output","call_id":c.call_id,
                                    "output": run_tool(c.name, c.arguments)})   # errors returned as text
    tool_calls += len(calls); cumulative_input += usage.input_tokens
    next call uses tool_choice="none" if tool_calls >= 10 or cumulative_input >= cap
```
- Enforce year scope in code: the run's year range is intersected with the model's `years` argument, and `read_pages` refuses pages outside the scope. Also tell the model in the user message.
- Citations: tool output follows the citation-formatting guide. Each read page gets `Citation Marker: citeturn{N}file{M}`, and code maps `turnNfileM → page_id → label`. The UI must hold back or strip the private-use marker characters while `output_text.delta` streams. Live: the model used 2 valid markers at low effort. It cited only 2 of the 3 pages it read, and put markers after bold text rather than after punctuation.
- `report_status` (spec §4.1) was not tested. Candidate: a third strict tool `report_status(status: enum)` handled like the others (I).
- Budget per question (I, from 1 live run): about $0.027 (3 calls, 3 pages, effort low) ≈ 38 KRW. Cache writes add 0.25× on tokens written in the final call that are never read back.

## 10. Unknowns / not verified
- Whether the API rejects `item.model_dump()` replay (extra `async_` key). Use `to_dict()`.
- Why the `encrypted_content` in `output_item.done` differs from the terminal event's copy, and whether the `done` copy also replays fine (only the terminal copy was tested).
- A run where the model calls tools **and** finishes with a strict `json_schema` answer while `text.format` is set from call 1 (the table-feature pattern). Only one request with both was tested, and it made no tool call.
- `tool_choice="none"` forced final answer on this model (not exercised live).
- What a GPT-5.6 safeguard block or refusal looks like in the stream (`response.failed`? refusal content?). Never triggered.
- Reasoning summaries (`reasoning.summary`) for a "생각 중" UI line: event names are known, availability for this account is not.
- How often `phase: "commentary"` preambles appear with our prompt (none seen in 4 message-producing calls).
- Whether spend-limit 429s carry `x-should-retry: false`.
- Minor environment issue: `uv pip install` left an empty `h11` package directory in this venv and a `--reinstall` fixed it. Watch for the same failure when building the HF Space image (I).
