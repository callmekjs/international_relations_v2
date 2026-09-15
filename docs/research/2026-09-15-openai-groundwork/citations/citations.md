# Plan 2 groundwork: how answers cite printed pages (gpt-5.6-sol)

Date: 2026-09-15. No live API calls were made for this note (spend $0.00).
Folder: `scratchpad/plan2/citations/` (all paths below are relative to it).

Doc pages were fetched as server-rendered HTML with curl and converted to text in `docs/*.txt`, so
the exact wording can be checked at the line numbers given. No page needed JavaScript. To respect
copyright, doc content is **paraphrased** here with URL, heading and local line numbers; only one short
phrase is quoted.

---

## 1. Confirmed: OpenAI does not return validated citations for our own tool outputs

| # | Fact (paraphrase unless quoted) | Source |
|---|---|---|
| F1 | A citation system is built by the app: you choose citable units, present them, instruct the model, and "validate the result before it renders to the user". | https://developers.openai.com/api/docs/guides/citation-formatting , Overview (`docs/citation-formatting.txt` L1356) |
| F2 | The guide closes by noting that *OpenAI-hosted* tools (e.g. web search) give automatic inline citations; the rest of the guide is about prompting and parsing your own markers. | same page, final note (L2105-2107) |
| F3 | A function tool result (`function_call_output`) is normally a string in any format you choose, which the model interprets; image/file arrays are the only alternative. No citation-bearing block type is described. | https://developers.openai.com/api/docs/guides/function-calling (`docs/function-calling.txt` L3636-3638) |
| F4 | Web search returns `url_citation` annotations (URL, title, location); file search returns `file_citation` annotations. | https://developers.openai.com/api/docs/guides/tools-web-search (L1588), https://developers.openai.com/api/docs/guides/tools-file-search (L1991) |
| F5 | Official Python SDK `openai` 3.14.0 (installed from PyPI into `.venv-sdk`): `ResponseOutputText.annotations` is a union of only `file_citation`, `url_citation`, `container_file_citation`, `file_path`; `FunctionCallOutput.output` is `str` or a list of `input_text` / `input_image` / `input_file`. | `.venv-sdk/Lib/site-packages/openai/types/responses/response_output_text.py`, `response_input_item_param.py` (class `FunctionCallOutput`), `response_function_call_output_item_param.py` |

**Conclusion (verified from F1-F5):** annotations come only from hosted tools. For our `search` / `read_pages` / `get_toc` function tools, the model's citations are plain text we must parse and check ourselves. (Not verified: whether passing a page as `input_file` in a function output would ever yield `file_citation`; nothing in the docs says so, and it would not give page-level ids anyway.)

## 2. OpenAI's recommended marker format and parsing advice (paraphrased)

Source: https://developers.openai.com/api/docs/guides/citation-formatting

- **Citable unit** (L1370-1390): document, block, or line range; block-level is called the best default for most systems (easier than lines, more useful than whole documents). A unit needs a stable id, readable text, optional metadata (L1392-1400).
- **Marker** (L1426-1462): start char U+E200, family word `cite`, delimiter U+E202, source id (e.g. `turn0file1`), optional locator (e.g. `L8-L13`), stop char U+E201. OpenAI says these markers closely match what its models were trained on and strongly recommends them; if you change marker values, keep the overall shape (L1426-1428). For tool calls, the `turnN` counter goes up once per tool invocation (L1444-1450).
- **Why familiar formats** (L1466-1470): custom formats raise the model's load and cause citation errors, especially at low reasoning effort and on complex tasks.
- **Ids vs locators** (L1413-1418): the model should emit the source id; your system should resolve/render the locator. Mixing the two early increases formatting errors.
- **Prompt rules for retrieved tool context** (L2025-2046): one marker per supporting source; do not write ids outside markers; put the marker at the end of the supported sentence, after punctuation; cite only sources that directly support the text; never invent ids or locators the tool did not return; cite all materially supporting sources; describe conflicts.
- **Parsing** (L1538-1546, L1972): regex from start char through family and delimiter to stop char; split the body on the delimiter; treat a trailing `L\d+(-L\d+)?` part as locator; reject parts that are not `[A-Za-z0-9_-]+`; keep character offsets so markers can be stripped afterwards (reverse order). Adjust the id regex if your ids differ. Our `page_id` ("2023-p050L") already fits that id regex.

## 3. Three designs compared (for gpt-5.6-sol, Korean text)

| | (a) inline page_id markers | (b) strict JSON: sentences + page_id + verbatim quote | (c) = (a) + code-only verification |
|---|---|---|---|
| Format familiarity (doc advice) | Best: OpenAI's trained marker shape | Custom structure, but **shape is enforced** by strict schema (no syntax errors possible); copying a quote is extra work | Same as (a) |
| Live streaming | Easy: stream `response.output_text.delta`, hold back text from U+E200 until U+E201 | Needs partial-JSON parsing. SDK 3.14.0 Responses stream helper parses JSON only at `response.output_text.done` (`openai/lib/streaming/responses/_responses.py` L294). `jiter` (installed with openai) parses prefixes: verified `jiter.from_json(prefix, partial_mode="trailing-strings")` returns `{'status': 'answered', 'sentences': [{'text': '한국은 2021'}]}`. Keys stream in schema order (structured-outputs guide L17076), so `text` arrives before its `citations` | Same as (a) |
| Korean | Marker chars are language-neutral; our sentence splitter must handle Korean endings and dates like "2018.4.27" | Model does the sentence split; JSON strings hold Korean as-is | Same as (a) |
| Invented / unread page_id | Only code can catch | Schema `pattern` blocks malformed ids; code catches unread ids | Code catches |
| Wrong but read page | **Undetectable** (no text to compare) | Detected: quote not on cited page; if verbatim on another read page, code can point to that page | Only weak signal: numbers/Latin words of the sentence missing from page |
| Paraphrased "quote" | n/a | Main risk. Code detects it; light edits are shown as "원문과 조금 다름" with the original text; heavy edits become "근거 없음" (fails safe) | n/a |
| Evidence text shown to user (spec 6.2 "인용 문장") | Must be guessed by code | Exact span cut from our own page text | Guessed by code (test shows it picked "제2절" for one sentence) |
| Extra cost | none | Quote output tokens: roughly (quote chars x tokens-per-Hangul-char) x $20/1M. Example if 1 token/char: 8 x 50 chars = 400 tokens = $0.008 (~11 KRW) per answer (**inferred**; ratio to be measured by the token-cost task) | none |
| Reuse for summary / table / compare | Prose only | Same verifier checks table/compare cells (spec 5.3) | Prose only |

**Recommendation: (b) + the code verifier (`citation_check.py`).** Reasons: the project's promise is "every sentence can be checked against the page". Only (b) lets code prove that the shown evidence is on the cited page, and its failures fall to "근거 없음" instead of showing a wrong page as evidence. The doc's warning about custom formats is mainly about marker syntax, which the strict schema removes. Keep (c) as the fallback if a live check shows the model paraphrases quotes too often (the verifier already parses inline markers).

### 3.1 Exact output format

Responses API request field (shape verified in SDK type `ResponseFormatTextJSONSchemaConfigParam`):
`text={"format": {"type": "json_schema", "name": "cited_answer", "strict": True, "schema": ANSWER_SCHEMA}}`
with `ANSWER_SCHEMA` exactly as in `citation_check.py`:

```json
{
  "type": "object", "additionalProperties": false, "required": ["sentences", "status"],
  "properties": {
    "sentences": {"type": "array", "items": {
      "type": "object", "additionalProperties": false, "required": ["text", "citations"],
      "properties": {
        "text": {"type": "string", "description": "답의 한 문장"},
        "citations": {"type": "array", "items": {
          "type": "object", "additionalProperties": false, "required": ["page_id", "quote"],
          "properties": {
            "page_id": {"type": "string", "pattern": "^[0-9]{4}-p[0-9]{3}[LR]$"},
            "quote": {"type": "string", "description": "그 쪽 원문에서 그대로 복사한 15~100자"}}}}}}},
    "status": {"type": "string", "enum": ["answered", "not_found", "not_in_corpus", "refused"]}
  }
}
```

- `status` replaces the separate `report_status` signal of spec 4.1 and comes last (decided after writing).
- Strict-mode rules checked by `schema_problems()`: every object has `additionalProperties: false` and lists all properties as required (structured-outputs guide, "Supported schemas" L16914, L17022); `pattern` and `enum` are listed as supported (L16689-16718). The pattern matches all 2,136 corpus page_ids (test).
- Tools + `text.format` in one request: the official Agents SDK (`openai-agents` 0.22.2, `agents/models/openai_responses.py` L1005-1020 and `get_response_format` L2020-2033) sends `tools` and a strict `json_schema` text format together. **Not live-tested** here. Fallback with the same schema: a strict function tool `submit_answer` (function-calling form of Structured Outputs; its arguments stream as `response.function_call_arguments.delta`).
- Example answer:
  `{"sentences":[{"text":"국립외교원은 2021년 제8회 외교관후보자 정규과정을 약 46주 동안 운영했습니다.","citations":[{"page_id":"2021-p112R","quote":"2021년 ‘제8회 외교관후보자 정규과정’을 약 46주 동안 운영했다"}]},{"text":"정리하면 다음과 같습니다.","citations":[]}],"status":"answered"}`
- read_pages output: keep `page_id` first in each page block, then `label`, then the text lines, serialized with `ensure_ascii=False` so the model sees Korean characters it can copy (inferred good practice, not measured).

### 3.2 Exact system-prompt instruction text (proposed)

```
## 근거 인용 규칙
- 근거로 쓸 수 있는 것은 이 대화에서 read_pages 도구가 돌려준 쪽의 글뿐입니다. search 결과의 짧은 조각은 쪽을 찾는 데만 쓰고, 인용하려면 먼저 그 쪽을 read_pages로 읽으세요.
- 최종 답은 정해진 JSON 형식으로만 씁니다. sentences 배열의 항목 하나가 답의 문장 하나입니다.
- 백서 내용을 담은 문장에는 citations를 하나 이상 붙입니다. citation 하나에는 page_id와 quote가 들어갑니다.
- page_id는 read_pages 결과에 적힌 값을 그대로 옮겨 적습니다. 결과에 없던 page_id를 만들거나 고치지 마세요.
- quote는 그 쪽 글에서 문장을 뒷받침하는 부분을 그대로 복사한 15~100자의 이어진 한 구간입니다. 어미, 띄어쓰기, 숫자, 문장부호를 바꾸지 말고, 요약하거나 말줄임표로 건너뛰지 마세요. 줄이 바뀌는 자리는 공백 하나로 써도 됩니다.
- 한 문장을 여러 쪽이 뒷받침하면 쪽마다 citation을 따로 붙입니다. quote는 되도록 한 쪽 안에서 고릅니다.
- 문장에 쓰는 숫자, 날짜, 이름, 기관명은 quote에 있는 표기와 같게 씁니다.
- 근거가 필요 없는 연결 문장(예: "정리하면 다음과 같습니다.")은 citations를 빈 배열로 둡니다. 읽은 쪽에서 근거를 찾지 못한 내용은 쓰지 마세요.
- 마지막에 status를 정합니다: 답을 했으면 answered, 찾지 못했으면 not_found, 자료 범위 밖이면 not_in_corpus, 백서와 무관한 부탁이면 refused.
```

Fallback (c) text, if chosen: replace the JSON bullets with "사실을 담은 문장 끝(마침표 뒤)에 [U+E200]cite[U+E202]page_id[U+E201] 표시를 붙이고, 여러 쪽이면 [U+E200]cite[U+E202]id1[U+E202]id2[U+E201]로 씁니다. 표시 밖에 page_id를 쓰지 마세요." The program must insert the real characters with `chr(0xE200)` etc. (see risk R7).

### 3.3 Verifier policy (implemented in `citation_check.py`)

| Citation check, in order | Result |
|---|---|
| page_id not returned by read_pages (search-only, not_found, not_citable, invented, malformed) | id rejected (`not_read` / `unknown`) |
| quote shorter than 8 key chars | `too_short`, rejected |
| quote contained in the cited page (comparison key below) | `exact` -> **확인됨** |
| quote runs over the break into the adjacent read half-page | `joined` -> 확인됨, label "110쪽 ~ 111쪽" |
| quote verbatim on another read page | `exact_on_other_page` -> 확인됨 on that page when `fix_wrong_page=True` (default; count as a model error in evals) |
| similarity >= 0.85, same numbers (with minus sign) and Latin words, <= 6 changed chars | `near` -> **원문과 조금 다름**, evidence = original page text, `differences` lists changes (`accept_near=False` turns it into 근거 없음) |
| otherwise | `not_found` / `page_rejected` -> rejected |

Sentence badge = best valid citation; none -> **근거 없음**. Evidence shown in the UI is always our own page text, never the model's quote. Show badges only when `status == "answered"`.

Comparison key `cite_key(text)` = `match_key(text)` (after marking minus signs) with these extra folds: every hyphen/dash variant used as a separator removed (fixes "KNDA-CEIP-JIIA" vs "KNDACEIPJIIA"); every middle dot removed, not only between Hangul; quote marks and angle/corner brackets removed; tilde variants unified; full-width brackets to ASCII; `->`/`=>` to an arrow. A dash right before a digit that follows a space/bracket/comma is kept as a minus sign, because the corpus writes minus as an en dash ("미국 –3.5%", 2020-p006R). A test proves `cite_key` equals `match_key` plus exactly these folds on all 1,979 citable pages.

## 4. Verifier results

Run: `cd C:\international_relations` then `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe -m pytest <folder>/test_citation_check.py -v -s -p no:cacheprovider --rootdir=<folder>` -> **49 passed in 1.57s** (`test_output.txt`, which also holds the demo JSON and two probes).

Real pages used (12, all years): 2020-p006R, 2020-p057L, 2020-p057R, 2021-p112L, 2021-p112R, 2021-p134R, 2022-p025L, 2022-p025R (unread), 2022-p146R, 2023-p144L, 2024-p153R, 2025-p121L; plus 2020-p001L (not citable) and 2021-p999L / 2023-p999L (invented).

| case | cited | id | quote_status | grade (badge) | similarity | found_on |
|---|---|---|---|---|---|---|
| true_dot_num_paren_2020 | 2020-p057L | read | exact | verified (확인됨) |  |  |
| true_quote_marks_2021 | 2021-p112R | read | exact | verified (확인됨) |  |  |
| true_list_parens_2022 | 2022-p025L | read | exact | verified (확인됨) |  |  |
| linebreak_paragraphs_2020 | 2020-p057L | read | exact | verified (확인됨) |  |  |
| linebreak_table_2021 | 2021-p134R | read | exact | verified (확인됨) |  |  |
| linebreak_after_hyphen_2024 | 2024-p153R | read | exact | verified (확인됨) |  |  |
| hyphen_as_is_2021 | 2021-p134R | read | exact | verified (확인됨) |  |  |
| hyphen_as_space_2021 | 2021-p134R | read | exact | verified (확인됨) |  |  |
| hyphen_as_endash_2021 | 2021-p134R | read | exact | verified (확인됨) |  |  |
| hyphen_removed_2021 | 2021-p134R | read | exact | verified (확인됨) |  |  |
| dot_hangul_araea_2021 | 2021-p134R | read | exact | verified (확인됨) |  |  |
| dot_as_period_near_2021 | 2021-p134R | read | near | near (원문과 조금 다름) | 0.962 |  |
| minus_ascii_for_endash_2020 | 2020-p006R | read | exact | verified (확인됨) |  |  |
| minus_dropped_rejected_2020 | 2020-p006R | read | not_found | unsupported (근거 없음) | 0.963 |  |
| tilde_variant_2022 | 2022-p146R | read | exact | verified (확인됨) |  |  |
| prime_quotes_arrow_2023 | 2023-p144L | read | exact | verified (확인됨) |  |  |
| corner_brackets_2025 | 2025-p121L | read | exact | verified (확인됨) |  |  |
| brackets_swapped_2025 | 2025-p121L | read | exact | verified (확인됨) |  |  |
| altered_ending_near_2021 | 2021-p112R | read | near | near (원문과 조금 다름) | 0.964 |  |
| altered_range_sign_near_2024 | 2024-p153R | read | near | near (원문과 조금 다름) | 0.98 |  |
| altered_number_rejected_2021 | 2021-p112R | read | not_found | unsupported (근거 없음) | 0.913 |  |
| paraphrase_rejected_2021 | 2021-p112R | read | not_found | unsupported (근거 없음) | 0.817 |  |
| ellipsis_rejected_2021 | 2021-p112R | read | not_found | unsupported (근거 없음) | 0.686 |  |
| too_short_2020 | 2020-p057L | read | too_short | unsupported (근거 없음) |  |  |
| page_break_joined_2020 | 2020-p057L | read | joined | verified (확인됨) |  |  |
| wrong_page_read_2021 | 2021-p112L | read | exact_on_other_page | verified (확인됨) |  | 2021-p112R |
| unread_real_page_2022 | 2022-p025R | not_read | page_rejected | unsupported (근거 없음) |  |  |
| unread_not_citable_2020 | 2020-p001L | not_read | exact_on_other_page | verified (확인됨) |  | 2020-p057L |
| invented_id_true_quote_2023 | 2023-p999L | unknown | exact_on_other_page | verified (확인됨) |  | 2023-p144L |
| invented_id_fake_quote_2023 | 2023-p999L | unknown | page_rejected | unsupported (근거 없음) |  |  |
| malformed_id_2023 | "2023년 286쪽" | unknown | exact_on_other_page | verified (확인됨) |  | 2023-p144L |

Other tests (all pass): old gold needle `KNDACEIPJIIA` fails with `match_key` but passes with `cite_key`; near evidence is the original text ("운영했다", "7.1-12"); `accept_near=False`; sign/number changes list `missing_anchors` (["3","6"], ["2","46"]); a Hangul word swap (중앙아시아 -> 동남아시아) is only `near` with `differences` [["중앙","동남"]] (known limit); 7 changed chars -> rejected; literal newline inside a quote; `fix_wrong_page=False`; page-break join needs both halves read; not_found/not_citable ids never count as read; multi-citation sentence + shared reference numbers + uncited sentence -> 근거 없음; inline-marker parsing for (c) (5 sentences -> page_only, page_only, 근거 없음, page_only with missing "50", 근거 없음); marker inside a long sentence; key/position mapping equal to `cite_key` on all 1,979 pages; schema strict rules; no literal special characters in the source files.

Probes (`near_false_positive_probe.txt`, `near_edit_probe.txt`, offline): a random real 40-char quote from page A tested on another page B scored `near` 1/400 times in the same chapter (a genuinely repeated phrase) and 0/400 at random. Real quotes with random Hangul edits were accepted (exact/near) for 1-2 edits almost always, 4 edits in 40- and 80-char quotes almost always (20-char quotes 40/189), and 8 edits rarely (1/170, 5/174, 7/170).

## 5. Open risks

- R1 (not live-tested): `text.format` strict JSON together with function tools in the tool loop, and whether gpt-5.6-sol writes preamble messages that must also fit the schema. The reasoning guide's `phase` advice names GPT-5.5 and GPT-5.4 only (`docs/reasoning.txt` L3613-3618). Spend 1-2 dev calls on this first; fallback is the `submit_answer` strict tool.
- R2: the verifier proves the quote is on the page, not that the quote supports the sentence. A wrong claim next to a true quote still shows "확인됨"; the UI shows the quote beside the sentence and the gold eval checks key facts.
- R3: how often the model alters quotes is unknown until live runs. If many sentences land in near/근거 없음, tighten the prompt or switch to (c).
- R4: `near` accepts up to 6 changed chars when numbers and Latin words match, so a swapped Hangul name can pass as "원문과 조금 다름" (never "확인됨"). Show `differences` in logs; decide whether the UI shows near at all.
- R5: `exact_on_other_page` hides model mistakes from visitors; the eval report should count corrected and near citations separately.
- R6: table pages (e.g. 2021-p134R) interleave columns line by line, so a row quote may not be contiguous in our text; such cells may need row-level quoting. Joined evidence shows a space at the page break ("극동시 베리아", cosmetic).
- R7: tool-written files turned `\u` escapes into literal characters in this session (both .py files, same failure as `docs/에러노트.md` 2026-09-15). Fixed by rewriting them with a script and guarded by `test_sources_hold_no_literal_special_characters`. The plan must keep that guard and use `chr()` for U+E200-style characters.
- R8: `match_key` stays unchanged here. Plan 2 should add `cite_key` to `assistant/textnorm.py` and decide whether `tests/test_recall.py` gold checks and spec 5.3 cell checks use it.
- R9 (doc note): the structured-outputs guide suggests `gpt-6-astra` for new projects (L2266); the gpt-5.6-sol model page lists streaming, function calling and structured outputs as supported (`docs/model-gpt-5.6-sol.txt` L1531-1540), so the chosen model fits this design.
