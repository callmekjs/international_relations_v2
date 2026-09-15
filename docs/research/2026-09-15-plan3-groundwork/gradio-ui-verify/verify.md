# Verification notes: Plan 3 groundwork, topic gradio-ui

Date 2026-09-15. Verifier ran with no OpenAI calls and no Hugging Face account actions. Every server was bound to 127.0.0.1.

**Setup**
- Fresh venv: gradio-ui-verify/venv (uv, Python 3.12.10).
- Second venv: venv2, with the extras a Space build might add.
- Independent verifier app and raw SSE client: v/vapp.py, v/v2app.py, v/vclient.py.
- Copied from the repo at HEAD abd82f9: assistant/, tests/fake_llm.py, tests/corpus_factory.py. Copied from the researcher (as test input): bridge.py, render.py, slow_fake.py.
- Server logs: v/m/events.jsonl. Tracker hits: v/m/tracker.txt.

## A. Claims re-checked

| # | Claim | Verdict | Evidence (kind) |
|---|---|---|---|
| 1 | gradio 6.27.0 is the latest (2026-09-11), requires Python >=3.10, pins gradio-client==2.7.0, httpx<1.0,>=0.24.1, starlette<2,>=1.0.1, huggingface-hub<2,>=1.16.0 | confirmed | pypi.org/pypi/gradio/json. Last 6 releases by upload time end at 6.27.0; none yanked (doc) |
| 2 | openai 3.14.0 needs httpx2<3,>=2.7.0 | confirmed | pypi.org/pypi/openai/3.14.0/json (doc) |
| 3 | gradio 6.27.0 + openai 3.14.0 + bm25s + numpy install together; pip check is clean | confirmed | Fresh uv venv: httpx 0.28.1 + httpx2 2.13.0, fastapi 0.141.1, starlette 1.6.0, uvicorn 0.53.0, pydantic 2.13.5; "All installed packages are compatible" (experiment) |
| 4 | Spaces python_version defaults to 3.10; sdk_version picks Gradio | confirmed | huggingface.co/docs/hub/spaces-config-reference: "Defaults to `3.10`"; "All versions of Gradio are supported" (doc) |
| 5 | Gradio 6 moved theme/css/js/head to launch(); api_name=False became api_visibility="private"; show_api became footer_links | confirmed | gradio.app/main/guides/gradio-6-migration-guide; launch() signature has theme and css (doc + sdk-source) |
| 6 | ChatMessage metadata keys: title, id, parent_id, log, duration, status | confirmed | gradio/components/chatbot.py MetadataDict (sdk-source) |
| 7 | Thread+queue bridge: events arrive in order, about 10 ms lag on localhost | confirmed | vclient stream: 14 shown events, lags 7.5-41.1 ms (13 of 14 under 12 ms), completed 6.4 s (experiment). Browser paint lag not re-measured. In tab-2, 2 lines were painted after 2.5 s |
| 8 | Sync generators are closed via SyncToAsyncIterator.aclose(), which retries "already executing" for up to 60 s, so a tick is needed | confirmed | gradio/utils.py aclose(timeout=60.0, retry_interval=0.05) (sdk-source). Generator closed about 0.4 s after cut with 1 s ticks (experiment) |
| 9 | gr.Markdown and gr.Chatbot strip script, on* handlers and javascript: links, but load remote images | confirmed | v/vapp.py xss (see detail below) (experiment) |
| 10 | gr.HTML does not sanitize | confirmed | onerror ran; also svg-script and ontoggle ran (experiment) |
| 11 | gr.HTML {{value}} data is executed as JS | confirmed | v2app: value `${Object.assign(window,{__d_hb_exec:1})}` set the flag and rendered "[object Window]" (experiment) |
| 12 | Dataframe(datatype="str") is plain text; datatype="markdown" fetches images | confirmed | dfstr had 0 img and the raw text shown; dfmd fetched df-md.png and dfmd-md.png, no onerror flag (experiment) |
| 13 | esc() output in gr.HTML is inert | confirmed | esc cell had 0 img, no flag, no tracker hit (experiment) |
| 14 | Chatbot default buttons include share and copy_all; feedback defaults Like/Dislike | confirmed (nuance) | Code default is ["share","copy","copy_all"] (the docstring says share, copy_all); feedback_options=("Like","Dislike") (sdk-source) |
| 15 | gr.Request fields; session_hash is unique per page load | confirmed (nuance) | Docs say it. The frontend generates `session_hash=Math.random().toString(36).substring(2)` client-side and the server trusts it (sdk-source, see B3) |
| 16 | uvicorn defaults apply (proxy_headers=True, FORWARDED_ALLOW_IPS or "127.0.0.1,::1"); the right-most untrusted XFF entry wins | confirmed | http_server.py uvicorn.Config has no proxy args; uvicorn/config.py; proxy_headers.py uses reversed(), and "*" uses the first entry (sdk-source). XFF "203.0.113.7, 198.51.100.2" gave client_host 198.51.100.2 (experiment) |
| 17 | HF docs say nothing about XFF/proxy | uncertain | No HF page found. Gradio docs also say nothing about Spaces for FORWARDED_ALLOW_IPS (doc search). See B6 for the X-IP-Token header that HF does document |
| 18 | Community Space reads the raw x-forwarded-for header | confirmed (weak) | radames/gradio-request-get-client-ip app.py uses the whole header string, not the first entry; last updated about 3 years ago (doc) |
| 19 | hmac.compare_digest can leak length but not value | confirmed | docs.python.org/3/library/hmac.html (doc) |
| 20 | gr.State is server-side; a client-sent value is ignored | confirmed | blocks.py preprocess: `if block.stateful: processed_input.append(state[block._id])`. A fresh session that sent True got unlocked=False; an unlocked session that sent False got True (experiment) |
| 21 | default_concurrency_limit defaults to 1; max_size None means unlimited | confirmed | blocks.py queue() docstring; queueing._resolve_concurrency_limit (sdk-source) |
| 22 | Events sharing a concurrency_id use the lowest limit | confirmed (nuance) | Applied lazily at push (queueing.py line 313 create_event_queue_for_fn) and never raised again. 3 asks at limit 4 ran together; after one summary (limit 1, same id) was pushed, 3 asks ran one at a time (experiment) |
| 23 | time_limit applies only to .stream() | confirmed | blocks.py line 745 docstring; queueing.py is_finished uses time_limit only when streaming (sdk-source) |
| 24 | concurrency_limit=4 with 6 sessions: 4 start, 2 wait | confirmed | Starts at 1.07-1.12 s ×4 and 6.67 / 6.72 s ×2 (experiment) |
| 25 | max_size=20 with 30 joins: 24 accepted, 6 got 503 | confirmed | Parallel joins gave 24/6 with "Queue is full. Max size is 20 and size is 20." Sequential joins gave 28/2, because runs finish during the slow loop (experiment) |
| 26 | On disconnect the job is marked not alive and the iterator closed, but the worker thread keeps going | confirmed | queueing.clean_events sets alive=False and removes queued events (sdk-source). Naive bridge: cut 1.61 s, generator closed 1.97 s, worker ran all remaining turns and returned "answered" (5 turns) at 6.42 s (experiment) |
| 27 | Bridge that cancels on GeneratorExit stops the worker at its next event | confirmed | Cut 1.44 s, generator closed 1.80 s, cancel_raised 2.28 s, status error, turns 1 (experiment) |
| 28 | A real browser tab close fires demo.unload within tens of ms and the worker stops | confirmed | With the naive generator (BRIDGE_CANCEL_ON_CLOSE=0), unload alone ran +22 ms after close (found=True), and cancel_raised came +285 ms at the next event (experiment) |
| 29 | Stop button (queue=False fn + cancels) stops in under 1 s | confirmed | /cancel then the stop fn at cut 1.43 s: generator closed 1.83, stop fn 2.18, worker stopped 2.26 (experiment) |
| 30 | A cancelled run ends as status error with the unknown notice (alert_owner=True) and loses the usage of the aborted turn | confirmed | errors.py UNKNOWN alert_owner=True; loop.py appends a TurnRecord only after llm.turn returns; the verifier run recorded turns=1 while turn 2 had emitted "thinking" (sdk-source + experiment) |
| 31 | api_visibility="private" hides the endpoint from /info but raw queue/join still runs it | confirmed | join 200, completed success=True, in_info=False; /config still lists the dependency and its fn_index (experiment) |
| 32 | Default launch serves /monitoring/summary and /gradio_api/runs; the flags turn them off | confirmed (risk overstated) | v2app (no flags) gave 200/200; vapp (flags) gave 403/404. But the summary is aggregate queue analytics, run history is "saved privately in the browser", and only public endpoints are recorded (route_utils._record_run_history) (experiment + sdk-source) |
| 33 | GRADIO_SSR_MODE is True on Spaces; analytics defaults to True | confirmed | gradio.app/guides/environment-variables; blocks._resolve_ssr_mode, so an explicit ssr_mode=False overrides the env (doc + sdk-source) |
| 34 | DownloadButton serves a BOM CSV as an attachment | confirmed (source only) | routes.py serves non-XSS-safe MIME types as application/octet-stream with attachment; the BOM is file content. Not re-run (sdk-source) |
| 35 | Default theme font is LocalFont Source Sans Pro, then ui-sans-serif, system-ui | confirmed (nuance) | themes/default.py. "No Hangul" is misleading: the browser falls back per glyph, so Korean still shows, just in an uncontrolled font. The custom stack computed on .gradio-container as set (sdk-source + experiment) |
| 36 | At 375 px only 2 of 5 tabs show, the rest sit behind "More tabs" | confirmed | 질문답변 and 요약 in the bar; 표 뽑기, 비교 and 예시 모음 in overflow-dropdown; scrollWidth 375 (experiment) |
| 37 | Dark mode makes #555 hard to read | uncertain | Not re-tested |
| 38 | Heartbeat defaults to 15 s (GRADIO_HEARTBEAT_INTERVAL) | confirmed | utils.get_heartbeat_rate docstring mentions Kubernetes (sdk-source) |
| 39 | delete_cache, analytics_enabled on Blocks; pwa, mcp_server, footer_links, run_history, enable_monitoring on launch | confirmed | blocks.py signatures. Note that pwa defaults to on when launched on Spaces (sdk-source) |

**Claim 9 detail (Markdown and Chatbot)**
- Removed: script, onerror, ontoggle, javascript: href (href became null).
- Kept: `<form action=external>`.
- Fetched: px-*.png and md-*.png for both components.
- No window flags were set.

**Claim 10 detail (gr.HTML)**
- These ran: `<img onerror>`, `<svg><script>`, `<details ontoggle>`.
- Kept: the iframe (fetched), the form, and the javascript: href.

## B. New findings

1. **max_size is global.**
   - `Queue.__len__` sums the waiting events of every concurrency id.
   - While the paid queue was full (20 waiting), a join to a different, free endpoint (whoami, its own id) also got 503 "Queue is full".
   - So a full paid queue also blocks the example gallery, saved summaries and the password box, which goes against spec 6.3 layer 4. (experiment)
2. **Shared concurrency_id limits are order-dependent.**
   - The lower limit takes effect only after its event is first pushed, then stays until restart (B/A22).
   - All paid events in one id must use the same number. (experiment + sdk-source)
3. **gr.State unlock is bound to the client-chosen session_hash.**
   - The hash comes from `Math.random().toString(36)`, generated in the browser.
   - A second client that reused the unlocked session's hash (different User-Agent) got unlocked=True.
   - After a tab closes, session state is only marked for deletion after 3600 s (state_holder).
   - Consequences: never log, store or display session_hash (not in run records or the gallery), and give the unlock its own expiry. (experiment + sdk-source)
4. **Anonymous file upload is open.**
   - POST /gradio_api/upload accepted a 200 KB file on an app with no upload component.
   - max_file_size defaults to unlimited, and the response returned the absolute server path under %TEMP%/gradio/<hash>/.
   - On a public Space this is free disk filling and a path leak. Set launch(max_file_size="1mb" or smaller) and delete_cache. (experiment + sdk-source; the test file was deleted afterwards)
5. **Queue bypass via /gradio_api/run/predict depends on api_open.**
   - api_open defaults to `utils.get_space() is None`: open locally, closed on Spaces.
   - Locally, 6 concurrent /run/predict calls to the limit-4 ask all started at once, bypassing the queue.
   - Each returned after the first yield and the worker never started, because the first yield comes before stream_run.
   - Set demo.queue(api_open=False) explicitly so local tests match Spaces, and never start paid work before the first yield. (experiment + sdk-source)
6. **Hugging Face documents an X-IP-Token header.**
   - The Gradio client docs say HF infrastructure adds it "to all incoming requests to Spaces"; its value depends on the requesting user.
   - It is a candidate input for the first-deploy visitor-key probe, possibly harder to forge than XFF. Unverified on a CPU Space. (doc: gradio.app/docs/python-client/using-zero-gpu-spaces)
7. **Raw queue/join without an SSE listener still runs the job to completion.**
   - nolisten probe: start 0.2 s, 3 steps, end 1.72 s, with nobody listening.
   - No disconnect ever happens, so the bridge cancel and unload never fire for such bots.
   - In-function caps and the global stop are the only guard. This resolves the researcher's unknown. (experiment)
8. **The heartbeat default of 15 s is documented as slow in Kubernetes-style environments.**
   - Spaces run behind a proxy, so if proxy disconnects are not passed through, unload/cancel may wait for a failed heartbeat write.
   - Consider GRADIO_HEARTBEAT_INTERVAL of about 5 and measure on the first deploy. (sdk-source docstring; applicability inferred)
9. **Shared-venue collisions (inferred).**
   - At the presentation venue, audience members share one NAT IP. Chrome's reduced User-Agent strings are identical within a major version, and accept-language is often identical (ko-KR).
   - The researcher's key HMAC(day|IP|UA|accept-language) would merge them into one visitor: they share 3 questions, and 5 wrong password tries by any of them would lock the presenter's key for the day.
   - Mitigation within the user's "IP + browser info" rule: add a random per-browser id kept in gr.BrowserState (localStorage) to the hashed browser info. Clearing it resets caps, the same as changing the UA; the global stop still guards.
10. **Space build extras (uncertain).**
    - If the Space image installs gradio[oauth,mcp] plus spaces, resolution changes: the mcp extra pins pydantic<=2.12.5, so pydantic 2.12.5 instead of 2.13.5.
    - pip check was still clean with openai 3.14.0 (venv2).
    - Not confirmed what HF installs; check the first build log. (experiment + doc)
11. **The cancel hook (D6) should also run before a retry sleep.** llm_openai.turn emits "retrying" then sleeps. From the live check (3 requests in 20.5 s), stop latency with a turn-boundary check is about one turn, roughly 7 s. (sdk-source + repo doc)
12. **Mobile (inferred).** A phone that backgrounds the browser can drop the heartbeat, causing unload → cancel, while the quota was reserved at start. The visitor loses a question. Keep the reservation, but show a "멈췄어요 (창이 닫혀서)" status and log the cancel reason to measure how often this happens.
13. **Handler nesting in the prototype.** The prototype stops the worker when the outer ask generator closes only because CPython finalizes the inner stream_run generator by refcount. It works (observed "generator closed"), but ask's finally should call handle.stop() explicitly if the worker has not finished.

## C. Decisions that should change

**D9 (queue)**
- Do not rely on a small global max_size to protect paid work. It also rejects free events.
- Use demo.queue(api_open=False, max_size=a large backstop such as 200, default_concurrency_limit=1).
- Enforce the paid waiting limit in the app: count active and waiting paid runs; above N, reply "지금 붐벼요" without reserving quota.
- Every event with concurrency_id="llm" uses the same concurrency_limit.

**D10 (launch hardening)**
- Add max_file_size (for example "1mb"; no uploads are needed).
- Explicit pwa=False is already listed.
- Also set demo.queue(api_open=False).
- Monitoring and run-history risk is lower than stated. Disabling them is still fine.

**D11 (presenter password)**
- Unlock lives in gr.State but is bound to a client-chosen session_hash. Never store or log session_hash, and give the unlock an expiry (for example until KST midnight or 3 h).
- Replace the "5 failures = locked for the day per visitor" rule, which lets a shared-NAT audience lock out the presenter. Use a short cooldown per key (for example 5 failures, then 10 minutes) with a long random password (at least 16 characters).
- A lockout must never revoke an already unlocked session.

**D12 (visitor key)**
- Add X-IP-Token (hashed) to the first-deploy probe.
- Consider a gr.BrowserState random id as part of the "browser info" so audience members behind one NAT with the same browser are not merged.
