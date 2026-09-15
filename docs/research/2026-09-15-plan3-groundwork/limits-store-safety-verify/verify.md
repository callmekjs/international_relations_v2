# Verification notes: Plan 3 limits-store-safety (2026-09-15)

No OpenAI API calls, no Hugging Face account actions. The repo at `C:/international_relations` was only read; `git status` is clean.
Folder: `scratchpad/plan3/limits-store-safety-verify/`. Web copies are in `pages/`, re-run scripts in `rerun/`.

## Re-run experiments
| What | Result | Files |
|---|---|---|
| `test_limits_store.py`, the researcher's own tests | ALL PASSED. Same numbers: 13 × 300 KRW, then a stop; 25 admitted with 3,900 KRW held back; rebuild 18.3 s; month 41.4 s cold, 0.287 s with day summaries | rerun/limits_store_results.json |
| `render_safety.py` | ALL PASSED, same tag set | rerun |
| `replay_prototype.py` on runs/*.json | Same totals: 20.48 / 10.24 s and 8.36 / 4.18 s. **Computed from sleep amounts, not timed with a clock.** For v1 records the total equals `elapsed_s` by construction | rerun/replay_results.json |
| Adversarial tests on the prototype (new) | (a) A run that never calls finish leaves the visitor `busy_visitor` 6 h later. 27 such runs hold 3,900 KRW, so a new visitor gets `daily_stop` with 0 KRW spent. (b) 40 new browser ids from one IP get 200 password tries. (c) A 900 KRW run that crosses KST midnight adds 0 to today's spend (it is counted only in the month total). (d) One IP + one UA with rotating browser ids gets 30 questions, not 3 | rerun/adversarial_limits.py, adversarial_limits_results.json |
| gr.HTML template logic, copied into node from `HTML-BMmdKPIw.js` | Default `${value}` template: payload **not** run. Any `{{value}}` / `{{{value}}}` in `html_template`: a `${...}` payload **runs**, even after Python `html.escape`. Turning `$` into `&#36;` stops it | gr_html_template_check.js, _output.txt |
| `pip install --dry-run` of openai==3.14.0 + gradio==6.27.0 | Installs together: httpx 0.28.1 + httpx2 2.13.0, uvicorn 0.53.0, fastapi 0.141.1. Only checked that pip can install them together; nothing was imported | resolve_report.json |

## Verdicts, in short (URLs are in the StructuredOutput)
- **Versions.** gradio 6.27.0 (2026-09-11; wheel sha256 6f4b9057… matches PyPI), huggingface_hub 1.31.0, uvicorn 0.53.0: confirmed.
- **Repo facts:** confirmed. These are: checks before any API call, `usage.cost_krw`, the `hash_identifier("local")` default, moderation returning `[]` on failure, no event timestamps, test lines 43/117, the question sent as the user message.
- **gr.HTML unsanitized (innerHTML, no sanitizer):** confirmed. **Missed:** the template is re-evaluated as a JS template literal (see above).
- **run_history default True, saves inputs:** confirmed, with a refinement. The client records history only when `api_visibility === "public"` (index-CRMvpSRm.js). Private events are not recorded even with run_history on. There is no password exclusion.
- **api_visibility "private":** only removed from api_info/docs. No server-side check was found in routes/queueing, so raw HTTP can still call it (confirmed from source, not tested live).
- **BrowserState:** confirmed, with a correction. The `secret` is sent to the browser, which decrypts it (Index-5wzl1T9Y.js), so it hides nothing from the visitor. `storage_key` is **also** random per start, so both must be fixed. Never reuse VISITOR_SALT as that secret.
- **FORWARDED_ALLOW_IPS:** Gradio docs say "127.0.0.1"; uvicorn falls back to "127.0.0.1,::1". Gradio passes neither to uvicorn.Config: confirmed. What the client IP looks like on Spaces is still uncertain (no primary doc).
- **OpenAI policies:** confirmed.
  - Usage Policies effective 2025-10-29.
  - Services Agreement effective 2026-01-01: §2.2, §3.2, §3.3(c) ("minors" not defined), §16.12, definition of OpenAI Policies.
  - 208 supported countries including South Korea; the page warns of account block or suspension.
  - Sharing policy 2022-11-14.
  - safety_identifier up to 64 characters; a "session ID" is allowed for logged-out previews.
  - A blocked identifier cannot be unblocked.
  - Data kept 30 days for abuse monitoring; not used for training unless the org opts in.
  - Per-user limits recommended; `project_spend_limit_exceeded`, which resets with the monthly cycle.
  - GPT-5.6 may pause mid-stream; agent-safety guidance.
- **HF:** confirmed.
  - Content policy 2025-04-10; ToS "solely responsible".
  - Protected needs PRO and the app stays public.
  - "Each time a new commit is pushed, the Space will automatically rebuild and restart".
  - cpu-basic sleeps after 48 h.
  - Disk is lost on restart; buckets mount read-write, keep no versions, and deletes are permanent.
  - Volume mounts are the "same idea as hf-mount".
  - hf-mount default writes are append-only and upload on close; O_TRUNC; up to 10 s stale; last writer wins.
  - CommitScheduler: at least 5 min between commits; batch_bucket_files is not all-or-nothing.
  - **Missed:** hf-mount's NFS backend (used where there is no /dev/fuse) always uses advanced writes with a delayed flush (2 s, up to 30 s). Rows written just before a restart can be lost.
- **MOFA:** confirmed.
  - Posts 291/292/298/299/300/301 return HTTP 200, with the titles and post dates as reported. The board's PDF names match corpus/volumes.json exactly.
  - 271 = 2018 edition, 290 = 2020 edition.
  - The footer carries the rights sentence. The "공공누리 인증" footer mark sits inside an HTML comment, so no post has a KOGL mark.
  - **Missed:** the MOFA copyright policy itself cites 저작권법 제24조의2 (free use of works the State created in its duties). Only the 2021 edition's colophon credits photos to 청와대.
- **Copyright Act Art. 28/37:** confirmed (easylaw). Easylaw notes an amendment taking effect 2026-10-29. Missing a source line can be fined up to 5 million KRW.
- **PIPA articles:** uncertain. The researcher's copy is the 2023-09-15 version. Act 21445 took effect **2026-09-11** (a secondary blog; the changes seem to be breach notices, the privacy officer and fines). Recheck on law.go.kr.
- **AI Basic Act:** confirmed. It took effect 2026-01-22. The current text is Act 21311 (in force 2026-07-21). Art. 2(7) defines 인공지능사업자 as "사업을 하는 자" and includes individuals. Art. 31(1)(2) as reported. The government has promised at least a year before fines (secondary source); the duties themselves already apply.
- **OWASP CSV:** confirmed.
- **"5 wrong passwords then locked":** refuted as a protection. It is per visitor key, and browser ids rotate.
- **"A cut stream that cost money still counts":** partly refuted for the real code.
  - `loop.run_agent` returns on LLMError without adding the failed turn, so that turn's tokens are never priced.
  - A cut or timed-out turn adds 0 KRW, while OpenAI may still bill it.
  - Timeout, connection and server_error runs with 0 KRW are refunded, although they may have been billed.
- **"Worst-case overshoot about 2 × 1,350 KRW":** uncertain.
  - If every input token were billed at the cache-write price, one QA run under QA_CAPS would cost about $1.20 (1,680 KRW).
  - "2 in flight" holds only if all LLM events share one `concurrency_id`. Separate `concurrency_limit=2` per tab allows 8.

## New findings (short)
1. **gr.HTML template-literal injection** (explained above): keep the default template and escape `$` as well.
2. **Tickets that never finish** block visitors all day and can close the day at 0 KRW. Gradio sets `job.alive=False` on disconnect (routes.py 1668, queueing.clean_events) and has a `/cancel` route. Settle in the worker thread with try/finally and expire stale tickets.
3. **Password lockout bypass** (200 tries). Use a long random password and slow down tries per IP. Do not lock globally: someone at the venue could then lock the presenter out.
4. **Spend under-count** on failed turns (loop.py). Charge the reserve on stream_broken/timeout/connection/server_error/unknown. Refund only busy (429), budget, config_error and bad_request.
5. **IP cap of 30 runs ≈ one abuser can use the whole daily budget.** Tables/compare cost 500–1,000 KRW, so 4–8 runs from one incognito user close the 4,000 KRW day. Carrier NAT also merges many people under one IP. Use a per-IP KRW cap (about 1,000 KRW) and log ip_cap refusals.
6. **September budget arithmetic.** The public launch is about 9/19, and 12,600 KRW covers the whole period to 9/28 plus 2 days. At 4,000 KRW/day the month stop can hit before the talk. A September daily stop of about 1,400 KRW, or relying on the presenter bypass, keeps visitors live longer.
7. **BrowserState** (above): fix both `storage_key` and `secret`; they are public values.
8. **Gradio disk-filling attack:** `/gradio_api/upload` has no size limit unless `max_file_size` is set, even with no file component (routes.py upload_file). Set `launch(max_file_size="1mb")`.
9. **`enable_monitoring=None`** (the default) leaves `/monitoring/summary` open: function names, request counts, latency percentiles. Set `enable_monitoring=False`.
10. **Put all LLM events in one `concurrency_id`** so the overshoot bound and the queue math hold.
11. **No code limit on quote length.** The prompt only asks for "보통 20~60자". A verbatim-copy request would show long white-paper passages under 확인됨. Cap shown quotes (for example 80 characters) and add a prompt rule. Art. 28 weighs 분량.
12. **safety_identifier = HMAC(IP|UA)** collides for identical phones on the venue Wi-Fi or carrier NAT. One block then hits unrelated people forever. OpenAI allows a session id for logged-out previews. Use HMAC(IP + browser_id), and on "identifier blocked" also block that IP key for the day.
13. **The OpenAI org can be warned, then lose GPT-5 access after about 7 days** of repeated high-risk requests (safety-checks.md). Abuse through the public demo can reach the owner's dev project. Watch the account email.
14. **OpenAI may delay streaming** for a flagged user (safety-checks.md). Also, the sharing policy says to "use good judgment" when "taking audience requests for prompts". Add both to the run-book.
15. **Notice wording.** Korean minors are under 19 (민법 제4조), and Services Agreement §3.3(c) does not define "minor". Write "만 19세 미만", which covers OpenAI's under-18 guidance too. Also confirm the org has not opted in to data sharing before stating "학습에 쓰지 않습니다".
16. **Deleting run records "at startup" never happens** if the Space runs 30+ days. Delete on KST rollover instead.
17. **The replay "measurement" proves no timing realism for v1 records.** Only the v2 `t` patch does; its 1-line change is correct.
