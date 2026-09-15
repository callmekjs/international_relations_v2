# Plan 3 groundwork digest: evidence behind decisions P1-P35 (2026-09-15)

Companion to `README.md` (Korean). This file holds the evidence: claims, sources, measured numbers, every refuted and
uncertain claim with its resolution, cross-topic conflicts, and the rationale for each spec change S1-S22.

Paths in this file are relative to `docs/research/2026-09-15-plan3-groundwork/`. A few referenced items were not
copied into the repository: virtual environments, web page copies (`*/pages/`, `hf-spaces/refs/`), the verifier app
folder `gradio-ui-verify/v/`, non-text-extension files such as `deps/emulate_space_build.sh`,
`limits-store-safety/runner_timestamps.patch` and `*.log`. README section 7 lists what was copied and what was left out.

## 0. Scope, method, labels

- Five research topics, each followed by an adversarial verifier: `gradio-ui`, `hf-spaces`, `deps`, `summary`,
  `limits-store-safety`. Where a verifier refuted or corrected a researcher, the verifier wins.
- No OpenAI API calls, no Hugging Face account actions, repository `C:/international_relations` read only
  (`git status` clean before and after in every topic). All servers bound to 127.0.0.1. Fake keys and
  `https://mock.invalid/v1` / `httpx2.MockTransport` for SDK checks.
- Researcher report.md files were not written (the harness blocked subagent report files); verifier notes exist as
  `<topic>-verify/verify.md`. The researcher reports live only in the orchestrator's result JSON.
- Labels: **doc** (official documentation or PyPI metadata), **sdk-source** (read in an installed wheel or the repo),
  **experiment** (run in a scratch venv), **inferred** (reasoning, not observed). "3P" marks third-party or forum sources.
- Versions checked on 2026-09-15: gradio 6.27.0 (uploaded 2026-09-11, latest, Requires-Python >=3.10),
  gradio-client 2.7.0, openai 3.14.0 (2026-09-14 23:29 UTC), httpx2 2.13.0 (2026-09-14), httpx 0.28.1,
  huggingface_hub 1.31.0 (2026-09-10), uvicorn 0.53.0, fastapi 0.141.1, starlette 1.6.0, numpy 2.5.3
  (Requires-Python >=3.12), bm25s 0.3.11, mcp 1.30.0 (2026-09-07; 2.2.0 exists but gradio caps <2), spaces 0.51.3,
  datasets 5.0.1. Sources: `https://pypi.org/pypi/<name>/json`.

## 1. Verification tally

Counts are from the verifiers' structured verdict lists (researcher claims re-checked).

| Topic | Confirmed | Refuted | Uncertain | Total |
|---|---|---|---|---|
| gradio-ui | 35 | 0 | 2 | 37 |
| hf-spaces | 26 | 1 | 1 | 28 |
| deps | 23 | 1 | 2 | 26 |
| summary | 30 | 2 | 4 | 36 |
| limits-store-safety | 31 | 2 | 5 | 38 |
| **Total** | **145** | **6** | **14** | **165** |

`gradio-ui-verify/verify.md` has a longer table (39 rows, 37 confirmed / 2 uncertain) because some rows split one claim.

## 2. Cross-topic conflicts and how they were resolved

| # | Conflict | Resolution | Why |
|---|---|---|---|
| C1 | Queue `max_size=20` (hf-spaces H11, gradio-ui D9, limits) | `max_size=200` backstop + app-level "busy" check (P13) | gradio-ui verifier B1 (experiment): `Queue.__len__` sums all concurrency ids; with the paid queue full, a free endpoint also got 503 "Queue is full". Small max_size breaks spec 6.3 layer 4 |
| C2 | Different per-event limits: hf-spaces qa 4 / summary 2 / table 1 / compare 1; limits 2; gradio-ui 4 | One `concurrency_id="llm"`, one number (4) for every paid event (P13) | gradio-ui verifier A22/B2 (experiment + sdk-source `queueing.py` line 313): lowest limit in a shared id applies lazily at first push and stays until restart (3 asks ran together, then 1 at a time after one limit-1 summary). Separate ids with limit 2 each allow 8 in flight, which breaks the overshoot bound (limits verifier) |
| C3 | Space requirements: 4 top-level pins (hf-spaces template) vs 55-pin lock (deps) vs 76-pin lock (deps verifier) | 76-pin lock everywhere (P1) | deps verifier E12: the build's last step installs unpinned mcp/authlib/spaces; the 76-pin lock makes that step a verified no-op. 4 pins let pydantic go 2.13.5 -> 2.12.5 silently |
| C4 | Gallery and seed summaries on the bucket (hf-spaces H5) vs in the deploy bundle (limits, hf-spaces verifier N4) | Bundle, read-only; bucket for runtime writes only (P5) | A broken or read-only mount (H7 degraded mode) would otherwise remove the zero-cost fallback |
| C5 | Salt: `VISITOR_HASH_SALT` Secret (hf-spaces), `VISITOR_SALT` Secret or `state/salt.hex` in bucket (limits), derive from PRESENTER_PASSWORD (gradio-ui option) | Secret `VISITOR_SALT` (P16) | Works in degraded mode (no bucket), survives password rotation, never shown (Secrets are unreadable after saving, doc spaces-overview) |
| C6 | Presenter lockout "5 failures = locked for the KST day per visitor" (gradio-ui D11, limits) | Long random password + per-IP-day throttle, no lockout, 3 h unlock expiry (P21) | limits verifier: 40 browser ids from one IP gave 200 tries; gradio-ui verifier B9: shared NAT lets the audience lock out the presenter |
| C7 | IP source: rightmost XFF (hf-spaces verifier), "client.host if public else last public XFF" (limits), X-IP-Token (gradio-ui verifier) | Rightmost public XFF entry, fallback client.host; ssr_mode=False; confirm by probe (P12, P17, U1) | Behaviour depends on SSR (deps/hf-spaces verifiers); HF proxy undocumented; leftmost entry spoofable; "last public" guards against private internal hops |
| C8 | Summary "new summary counts only on success" (summary) vs "reserve quota at start" (gradio-ui D5, limits) | Reserve at start, one refund rule for all tasks; store hits and lock-joined results cost nothing (P18, P19) | Parallel starts must not exceed caps; one rule is simpler to test |
| C9 | Cancel on tab close (gradio-ui D4) vs detached summary generation (summary verifier N7) | QA cancels at turn boundaries; first-time summary generation is detached and always saved (P8, P9) | QA remaining turns are pure waste after close; an interrupted single-turn summary wastes tokens already generated and saves nothing |
| C10 | `safety_identifier`: daily-rotating visitor hash (spec 4.3), stable HMAC(IP\|UA) (limits), HMAC(IP\|browser_id) (limits verifier) | Stable HMAC(salt, "s\|IP\|browser_id") (P23) | OpenAI wants a stable id and cannot unblock; IP+UA collides for identical phones behind NAT |
| C11 | `store_selfcheck` synchronous before launch (hf-spaces H7) | Daemon thread after launch, 60 s limit (P6) | hf-spaces verifier N6: FUSE calls with no timeout can hang startup |
| C12 | Per-IP soft cap 30 runs (limits) | Per-IP-day KRW cap about 1,000 (P20) | limits verifier: 4-8 table/compare runs from one IP close the 4,000 KRW day |
| C13 | Monthly visitor stop 12,600 KRW (limits) vs verifier note that it may trigger before 9/28 | Kept as a proposal needing the owner's confirmation (P22) | Without it the shared public-project hard limit ($12) can block the presenter too |
| C14 | Adapter timeout 180 s (QA) vs 600/900 s for summaries | QA keeps 180 s; summary standard 600 s, flex 900 s (P29, P30) | With `stream=True` the SDK timeout is a per-read inactivity timeout (summary verifier #33, sdk-source `_base_client.py`); long silent reasoning or flex queueing may exceed 180 s |
| C15 | Ledger sketch adds presenter spend to visitor total (hf-spaces researcher) | Presenter spend recorded separately (P21) | Spec 6.3 layer 3 counts "방문자 사용 합계"; hf-spaces verifier L2 |
| C16 | `usage_ledger_sketch` has no in-flight reservation (hf-spaces) vs `limits_store.py` reserve-then-settle | Reserve-then-settle (P18) | hf-spaces verifier L2: budget 100, 10 parallel grants, 900 KRW |

## 3. Evidence per decision

### 3.1 Install and deploy

**P1 - 76-pin lock (repo `requirements.txt` = Space `requirements.txt`; prep file = `-r requirements.txt` + pymupdf + pytest)**
- Co-install: `pip install gradio==6.27.0 openai==3.14.0 bm25s==0.3.11 numpy==2.5.3 pytest` on CPython 3.12.10:
  exit 0, no backtracking, `pip check` "No broken requirements found", 60 packages; verifier's fresh venv freeze is
  identical (experiment; `deps/freeze.txt`, `deps-verify/v1_freeze.txt`).
- 0 files owned by two distributions; `httpx/` vs `httpx2/`, `httpcore/` vs `httpcore2/` separate
  (experiment; `deps/file_collisions.txt`, `deps-verify/file_collisions_verify.txt`).
- `OpenAI(...)._client` MRO base is `httpx2.Client` (experiment; `deps/httpx2_client_check.txt`).
- One process: Blocks app + OpenAI client; gradio_client received 5-6 streamed updates in 1.46-2.3 s; GET / 200,
  `/config` version 6.27.0 (experiment; `deps/smoke_result_venv.json`, `deps-verify/smoke/result_v1_nossr*.json`).
- Build order on Gradio Spaces (3P doc: community build logs 2025-11-14 and 2025-12-19):
  `FROM python:3.10` -> pip -U + datasets -> apt -> Node setup -> `pip install -r requirements.txt` ->
  `pip install gradio[oauth,mcp]==<sdk_version> "uvicorn>=0.14.0" spaces`
  (https://discuss.huggingface.co/t/gertie01-hub-6oa42x9a-report/170468,
  https://discuss.huggingface.co/t/report-not-working/171762).
- gradio 6.27.0 extra `mcp` = `mcp<2.0.0,>=1.21.0` and `pydantic<=2.12.5,>=2.11.10` (doc: PyPI JSON).
  `gradio[mcp]==6.27.0` + `pydantic==2.13.5` is unsatisfiable (experiment; `deps-verify/uv_checks.txt` section C).
- Emulation A (freeze pins, pydantic 2.13.5): last step uninstalls pydantic 2.13.5 -> 2.12.5 and pydantic_core
  2.46.5 -> 2.41.5, pip exits 0; datasets 5.0.1 needs `fsspec<=2026.6.0` so fsspec 2026.7.0 breaks pip check
  (experiment; `deps/emul_A_log.txt`).
- Emulation B (pydantic 2.12.5, pydantic-core 2.41.5, fsspec 2026.6.0): last step changes none of our pins
  (experiment; `deps/emul_B_log.txt`).
- The last step still installs unpinned mcp/authlib/itsdangerous/spaces + deps. Adding their closure (21 pins: mcp
  1.30.0, authlib 1.8.0, itsdangerous 2.2.0, spaces 0.51.3, requests 2.34.2, urllib3 2.7.0, charset-normalizer 3.5.1,
  attrs 26.1.0, cffi 2.1.1, cryptography 50.0.1, httpx-sse 0.4.3, joserfc 1.7.5, jsonschema 4.26.0,
  jsonschema-specifications 2025.9.1, pycparser 3.0, pydantic-settings 2.15.0, pyjwt 2.14.0, python-dotenv 1.2.3,
  referencing 0.37.0, rpds-py 2026.6.3, sse-starlette 3.4.11) changes no existing pin; emulated build step 4 installs
  nothing; pip check clean (experiment; `deps-verify/requirements-space-with-step4.txt`, `v3_emul_log.txt`).
- Linux: `uv pip compile --python-platform x86_64-manylinux_2_28 --python-version 3.12` recompiles the lock to itself;
  union with the build-step packages changes 0 pins (experiment; `deps-verify/uv_checks.txt` A, B).
- Tests: fast suite on a `git ls-files` copy: 174 passed, 9 skipped, 2 deselected on pydantic 2.13.5 and on
  pydantic 2.12.5 (lock venv v2, 23.33 s) (experiment; `deps-verify/pytest_prep.txt`, `pytest_lock_v2.txt`).
  `tests/conftest.py` line 3 imports `prep.volumes`; a copy without `prep/` fails collection (experiment).
- `huggingface_hub 1.31.0` is already in the lock, so the `hf` CLI comes with it (hf-spaces H14; doc manage-spaces).
- Re-run `deps/emulate_space_build.sh` and the uv union compile whenever a direct pin changes (pip exits 0 even when
  it breaks preinstalled packages).

**P2 - Space README keys**
- `python_version` "Defaults to 3.10"; `sdk_version` selects Gradio; `suggested_storage`: "The persistent storage
  feature is no longer available"; preload of private repos "not supported yet"; `startup_duration_timeout` default
  30 min (doc: https://huggingface.co/docs/hub/spaces-config-reference).
- numpy 2.5.3 Requires-Python >=3.12 (doc: PyPI). Linux resolution of the app set: 3.10 exit 1, 3.11 "numpy==2.5.3 has
  no usable wheels", 3.12 exit 0 (71 packages), 3.13 exit 0 (+audioop-lts 0.2.2)
  (experiment; `hf-spaces/deps/py310_resolve_error.txt`, `deps/python_version_check.txt`, `hf-spaces-verify/deps/`).
- Template: `hf-spaces/space_template/README.md` (use it; ignore its 4-line requirements.txt).

**P3 - Allow-list bundle built outside the repo; `hf upload`; per-deploy approval**
- `upload_folder` / `hf upload` apply the root `.gitignore` (fallback: the one on the Hub), enforced server-side;
  skipped files logged only at info/debug. `DEFAULT_IGNORE_PATTERNS` = `.git`, `.cache/huggingface` only, not `.env`
  (doc: https://huggingface.co/docs/huggingface_hub/guides/upload; sdk-source huggingface_hub 1.31.0
  `_upload_pipeline.py:378-383`, `utils/_paths.py:25-33`).
- Repo `.gitignore` lists `corpus/`, `data/`, `.env`, `/runs/` (sdk-source: repo).
- Dry run of the real repo: 27 files, 15,980,226 bytes; largest `corpus/pages.jsonl` 4,941,214; `corpus/index/meta.json`
  3,964,067; two `.npy` 2,881,156 each; only issue: `app.py` missing (experiment; `hf-spaces/real_repo_dryrun.json`,
  verifier re-run identical). Fake repo: `.env`, `.gitignore`, `data/*.pdf`, `runs/`, `__pycache__` excluded; a planted
  key-shaped string made the script refuse (experiment; `fake_bundle_run1/2.json`).
- `git check-ignore --no-index` on `dist/space` inside the repo: corpus copy ignored, `app.py`, `assistant/*.py`,
  `README.md`, `requirements.txt` not ignored (experiment; hf-spaces verifier N7).
- `hf upload` does not delete remote files removed locally unless `--delete` patterns are passed (doc: upload guide).
- Key regex `sk-...{20,}` lacked a left word boundary (hf-spaces verifier N11; real repo 0 hits).
- Every push rebuilds and restarts the Space (doc: spaces-overview). Spec 6.1 already requires asking before each deploy.

**P4 - Corpus inside the Protected Space; never in allowed paths; 403 test**
- Protected: source code private to owner and collaborators, app public at `https://<subdomain>.hf.space`, not clonable;
  PRO/Team/Enterprise feature (doc: https://huggingface.co/docs/hub/spaces-overview, changelog
  https://huggingface.co/changelog/protected-spaces 2026-03-20).
- Gradio 6.27.0 serves only allowed/created/temp paths (`utils.is_allowed_file`). `/gradio_api/file=corpus/pages.jsonl`,
  absolute path, `app.py`, fake `.env`, `./corpus/...` all 403 in CSR; SSR proxy also 403 (other SSR paths return the
  HTML shell) (experiment; `hf-spaces-verify/gradio_probe/results.txt`).
- `preload_from_hub` cannot read private repos; a startup download would need a token (doc: config reference).
  Upgrade path if Public is ever wanted: private dataset mounted read-only `hf://datasets/<user>/whitepaper-corpus:/corpus:ro`.

**P5 - Private bucket at `/data` for runtime writes only; gallery and seed summaries in the bundle**
- Space disk is ephemeral; Storage Buckets attached as volumes are the recommended persistence; buckets mount read-write
  by default; non-versioned, deletes permanent (doc: https://huggingface.co/docs/hub/spaces-storage,
  https://huggingface.co/docs/hub/storage-buckets). Settings got a "Storage Buckets" section on 2026-03-31
  (doc: https://huggingface.co/changelog/storage-buckets-for-spaces).
- Volume API: `Volume(type, source, mount_path, revision, read_only, path)`; `set_space_volumes` replaces all volumes;
  CLI `hf spaces volumes set <id> -v hf://buckets/<u>/<b>:/data[:ro]` (sdk-source huggingface_hub 1.31.0 `_space_api.py:122`).
- PRO includes 1 TB private storage, then $18/TB/month; egress and CDN included up to an 8:1 ratio
  (doc: https://huggingface.co/docs/hub/storage-limits, https://huggingface.co/storage).
- Region: non-Team repositories are stored in the US and a Space's runtime uses that region (doc:
  https://huggingface.co/docs/hub/storage-regions); public API shows `region: "us"` (experiment).

**P6 - Create-once files, writer thread, in-memory counters rebuilt at startup, self-check in a thread**
- Spaces volume mounts are "the same idea as hf-mount" (doc: https://huggingface.co/docs/hub/storage-buckets-access).
  hf-mount README: streaming writes append-only, uploaded on `close()`, overwrite only with O_TRUNC; advanced writes
  flush async (2 s, at most 30 s); NFS backend always uses advanced writes ("A crash before flush completes means data
  loss"); locks local to one mount; metadata up to 10 s stale; last writer wins (doc: https://github.com/huggingface/hf-mount).
  Which mode Spaces use: undocumented.
- 3P experiment (HF staff probe Spaces, gradio 5.49.0, 2026-04-08): Gradio SDK app runs as uid 0, FUSE idmapped mount;
  touch, SQLite, flock succeed; Docker Space as uid 1000 fails every write (`hf-spaces/refs/`). Stay on the Gradio SDK.
- trackio on Spaces forces SQLite `journal_mode=DELETE`, `locking_mode=EXCLUSIVE`, one connection, in-process lock
  because file locks are unreliable (sdk-source: trackio `sqlite_storage.py` lines 90-118, 170-178).
- Prototype `limits_store.py` (experiment; `limits_store_results.json`, verifier re-run ALL PASSED): 64 simultaneous
  starts for one visitor -> 1 admitted; 200 simultaneous visitors -> 25 admitted, 3,900 KRW reserved; restart restored
  3,900 KRW visitor / 500 KRW presenter; torn file skipped. `usage_ledger_sketch.py`: 10 (researcher) and 50 (verifier)
  parallel reservations -> exactly 3.
- Rebuild cost on local NTFS: 2,000 fresh files 14-19 s (verifier 18.3 s); a month of 4,350 files 38-39 s cold
  (verifier 41.4 s), 0.27-0.287 s with per-day summaries. A lazy network mount will be slower (inferred).
- Self-check probes FUSE operations synchronously without an overall timeout (hf-spaces verifier N6, inferred from
  `store_selfcheck.py`); local NTFS run: everything OK except flock (no fcntl on Windows).
- Layout: `usage/<KST day>/<ts>-<id>.json` (row about 270 bytes), `usage/_days/<day>.json`,
  `runs/<day>/<ts>-<id>-<task>.json`, `summaries/{year}/ch{NN}/{prompt_version}/{model}.json`.

### 3.2 Screen

**P7 - Worker thread + queue -> generator bridge with 1 s ticks; server-built HTML in `gr.HTML`**
- Raw SSE client, fake 1.2 s turns: 14 events emitted and received in order, lag 9.1-15.3 ms, run 6.24 s
  (experiment; `gradio-ui/proto/measurements/stream_turn1.2.json`); verifier 7.5-41.1 ms (13 of 14 under 12 ms).
- Real Chromium: click to handler 44 ms; emit-to-painted 8.5-18.4 ms for all 14 lines in order
  (experiment; `browser_timing.json`).
- Gradio closes sync generators via `SyncToAsyncIterator.aclose(timeout=60.0, retry_interval=0.05)`, retrying while
  "already executing" (sdk-source gradio `utils.py` 897-922); with ticks the generator closed about 0.4 s after a cut
  (experiment, verifier).
- Generator outputs stream as per-output diffs (experiment; raw SSE dump). `show_progress="hidden"` avoids the
  spinner overlay.
- `gr.Chatbot` with `ChatMessage(metadata={title,status,duration})` also works but renders Markdown, defaults to
  share/copy/copy_all buttons and Like/Dislike feedback, and suggests follow-up chat (sdk-source `chatbot.py`).

**P8 - Three stop paths + `should_stop` hook in `assistant.run`, turn-boundary only, status `cancelled`, deadline**
- Naive bridge: connection closed 2.37 s, worker ran 13 more events (all 5 turns), finished "answered" 15.28 s
  (experiment; `disconnect_control_nocancel.json`); verifier: cut 1.61 s, worker ran all 5 turns to 6.42 s.
- Cancel flag on `GeneratorExit`: closed 2.44 s, generator closed 3.34 s, worker stopped 4.23 s
  (experiment; `disconnect_after4_turn3.json`); verifier cut 1.44 s, stop 2.28 s.
- Real tab close: `demo.unload(fn(request))` +51 ms (verifier +22 ms), worker stopped +81 ms (verifier +285 ms at the
  next event), generator closed +89 ms (experiment; `browser_tab_close.json`).
- Stop button (`queue=False` fn + `cancels=[event]`) pressed 2.43 s: handler 2.78 s, worker stopped 3.32 s
  (experiment; `stop_both_after4_turn3.json`); `/cancel` alone: worker stopped 4.19 s.
- Gradio on disconnect sets `job.alive=False` and closes the iterator; the worker thread is not stopped
  (sdk-source `routes.py` 1665-1670, `queueing.py` 649-656, 939-941, 1123-1136).
- Current behaviour when on_event raises: status `error`, notice `unknown` with `alert_owner=True`
  (sdk-source `assistant/errors.py` line 47), record kept 1 of 2 started turns because `loop.py` appends a
  `TurnRecord` only after `llm.turn` returns (experiment; `record-359340da.json`).
- `time_limit` applies only to `.stream()` events (sdk-source `blocks.py` line 745; `queueing.py` 94-96).
- The hook should also run before the retry sleep in `llm_openai.turn` (gradio-ui verifier B11); with turn-boundary
  checks stop latency is about one turn (live check: 3 requests in 20.5 s, so about 7 s; doc
  `docs/research/2026-09-15-first-live-check.md`).
- The outer handler's `finally` should call the worker handle's stop explicitly instead of relying on CPython
  refcount finalization of the inner generator (gradio-ui verifier B13).
- Mobile browsers that background the tab can drop the heartbeat and trigger unload (inferred, B12): log the cancel reason.

**P9 - Detached first-time summary generation with a per-key lock**
- For a synchronous response "To cancel a synchronous response, terminate the connection" (doc:
  https://developers.openai.com/api/docs/guides/background.md); tokens generated before the cut are presumably billed
  (inferred). Gradio cancel/disconnect behaviour varies by version (3P: gradio issues #8503, #6239, PR #10827).
- Background mode (`background=true` + `stream=true`, resumable with `starting_after`) is documented but stores data
  about 10 minutes and has higher time-to-first-token; flex compatibility undocumented (doc: background.md). Not adopted.

**P10 - Record v2**
- `runner.emit` stores `{"event": kind, **data}` without time; only `elapsed_s` exists (sdk-source `assistant/runner.py`
  lines 84-87, 103). Patch: `limits-store-safety/runner_timestamps.patch` (adds `"t"`, `RECORD_VERSION = 2`,
  `record["moderation"]`). `tests/test_runner.py` lines 43 and 117 compare the full `done` dict (sdk-source).
- Replay "measurement" (20.48 s -> 20.48 s at 1x, 10.24 s at 2x; 8.36 -> 8.36 / 4.18 s) is computed from sleep amounts
  and equals `elapsed_s` by construction for v1 records (limits verifier), so it proves no rhythm; v2 `t` is required.
- `session_hash` is generated client-side (`Math.random().toString(36).substring(2)`) and trusted by the server; a
  second client reusing an unlocked session's hash got `unlocked=True`; session state is kept 3600 s after close
  (experiment + sdk-source; gradio-ui verifier B3).

**P11 - Escaping and component choice**
- `gr.HTML` does not sanitize: `<img onerror>`, `<svg><script>`, `<details ontoggle>` executed; iframe fetched;
  `javascript:` href and external form kept (experiment; `gradio-ui/proto/xss_lab.py`, verifier `v/vapp.py`).
  Docs mention no sanitize option (doc: https://www.gradio.app/docs/gradio/html). Frontend bundle
  `templates/frontend/assets/HTML-BMmdKPIw.js` (109,375 bytes) uses innerHTML, no sanitizer (sdk-source).
- `gr.HTML` compiles `html_template` with Handlebars and evaluates the output as a JS template literal
  (`Function(...keys, "return \`" + r + "\`;")`). node replica (experiment;
  `limits-store-safety-verify/gr_html_template_check_output.txt`): default `${value}` -> payload not run;
  `<p>{{value}}</p>` -> ran; Python `html.escape` then `{{{value}}}` -> ran; escape + `$`->`&#36;` -> not run.
  gradio-ui verifier: `${Object.assign(window,{__d_hb_exec:1})}` in `{{value}}` set the flag.
- `gr.Markdown`, `gr.Chatbot`, `gr.Dataframe(datatype="markdown")`: script, on* handlers, `javascript:` removed; class/style
  and `<form action=external>` kept; remote `<img>` and `![](url)` fetched (tracker hits) (experiment).
  `sanitize_html=True` default (sdk-source `markdown.py:53`).
- `gr.Dataframe(datatype="str")`: HTML/Markdown shown as literal text, no fetch (experiment; `xss_lab2.py`).
- `esc()` (html.escape + backtick and `$` entities) in `gr.HTML`: no flags, no tracker hits; a Chatbot thought with the
  same HTML-escaped query still rendered a Markdown image and fetched it on every update (10 requests) (experiment).
- `limits-store-safety/render_safety.py`: 6 attack strings produced only section/span/p/sup/ol/li/q/a with
  class/value/href/target/rel and exactly one MOFA link (experiment, verifier re-run passed).

**P12 - Launch hardening bundle**
- Defaults exposed: `/monitoring/summary` 200 and `/gradio_api/runs` 200; `enable_monitoring=False` -> 403,
  `run_history=False` -> 404 (experiment; `probe_defaults.json`, `probe_misc.json`). Verifier: summary is aggregate
  queue analytics (function names, counts, latency percentiles), run history is stored in the visitor's browser and only
  for `api_visibility="public"` events (sdk-source `route_utils._record_run_history`, `index-CRMvpSRm.js`), so risk is
  lower than first stated but disabling is still right.
- Anonymous `POST /gradio_api/upload` accepted 200 KB with no upload component; `max_file_size` unlimited by default;
  response leaked the absolute temp path (experiment; gradio-ui verifier B4; sdk-source `routes.py upload_file`).
- `api_visibility="private"` hides from `/gradio_api/info` and gradio_client, but raw `POST /gradio_api/queue/join`
  with `fn_index` ran to completion; `/config` still lists the fn_index (experiment; `private_endpoint.json`). A join
  with no SSE listener also runs to completion (start 0.2 s, end 1.72 s), so no disconnect fires for bots
  (experiment; gradio-ui verifier B7).
- SSR: `GRADIO_SSR_MODE` defaults False except on Spaces where it is True (doc:
  https://www.gradio.app/guides/environment-variables); SSR runs a Node front proxy with Python on an internal port
  (sdk-source `blocks.py` about 3058); local SSR added node.exe 94.0-94.3 MB working set and about 0.5 s to first 200
  (experiment; `deps-verify/smoke/result_v1_ssr*.json`; hf-spaces verifier measured about 85 MB). Explicit
  `ssr_mode=False` overrides the env (sdk-source `_resolve_ssr_mode`).
- `GRADIO_ANALYTICS_ENABLED` defaults "True" and posts launch telemetry to `https://api.gradio.app/`
  (sdk-source `gradio/analytics.py` lines 31, 46); `analytics_enabled()` reads the env at call time, so
  `os.environ.setdefault` before `import gradio` works locally and on Spaces. Space Variables are publicly viewable
  (doc: spaces-overview), so a Variable is optional.
- `pwa` defaults on when launched on Spaces (sdk-source, gradio-ui verifier #39).
- Gradio 6 migration: theme/css/js/head on `launch()`; `api_name=False` -> `api_visibility="private"`; `show_api` ->
  `footer_links` (doc: https://www.gradio.app/main/guides/gradio-6-migration-guide).
- Consolidated sketch (to be implemented in `app.py`):

```python
import os
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")  # before importing gradio
import gradio as gr
with gr.Blocks(analytics_enabled=False, delete_cache=(3600, 3600)) as demo:
    ...  # every event: api_visibility="private"; paid events: concurrency_id="llm", concurrency_limit=4
demo.queue(api_open=False, max_size=200, default_concurrency_limit=1)
demo.launch(ssr_mode=False, footer_links=[], enable_monitoring=False, run_history=False, show_error=False,
            mcp_server=False, pwa=False, max_file_size="1mb", theme=..., css=...)
```

**P13 - Queue**
- `default_concurrency_limit` defaults to 1 (env `GRADIO_DEFAULT_CONCURRENCY_LIMIT`); `max_size=None` unlimited
  (sdk-source `blocks.py` 2672-2711; runtime print `max_size: None default_concurrency_limit: 1`).
- `concurrency_limit=4`, 6 sessions: 4 started at 1.07-1.12 s, 2 at 6.67-6.72 s (experiment, both).
- `max_size=20`, 30 parallel joins: 24 accepted, 6 HTTP 503 "Queue is full. Max size is 20 and size is 20."
  (experiment; `queue_full.json`); `max_size` is global across ids (verifier B1).
- `api_open` defaults to `utils.get_space() is None` (open locally, closed on Spaces); locally 6 concurrent
  `/gradio_api/run/predict` calls bypassed the limit-4 queue and returned after the first yield without starting the
  worker (experiment + sdk-source `blocks.py:1178`, `routes.py:1417`). Hence `api_open=False` explicitly and paid work
  only after the first yield.
- Why 4 (synthesis): real QA runs took 8-21 s and cost 20-50 KRW (live check); each running generator holds one thread
  of the 40-thread pool (gradio-ui risk note); reserve-then-settle (P18) bounds admission. The theoretical overshoot is
  4 x (task worst case - reserve), for example 4 x (about 1,500 - 150) KRW for QA under spec 4.4 caps; the OpenAI
  project hard limit remains the last guard. Lower to 2 if early usage shows expensive runs (inferred).
- The "busy" threshold (active + waiting paid runs > 12) is a synthesis value, configurable (inferred).
- Heartbeat default 15 s (sdk-source `utils.get_heartbeat_rate`, docstring warns about Kubernetes-like environments).

**P14 - Fonts, theme, tab order**
- Default theme font `LocalFont("Source Sans Pro")`, then `ui-sans-serif, system-ui` (sdk-source `themes/default.py`
  19-24); browsers fall back per glyph, so Korean renders in an uncontrolled font (verifier nuance). With the system
  Korean stack no request to fonts.googleapis.com and Gradio loaded its Korean locale (experiment). `GoogleFont()` would
  fetch from Google (sdk-source `themes/utils/fonts.py`).
- 375x812: no horizontal scroll (scrollWidth 375), only 질문답변 and 요약 visible; 표 뽑기, 비교, 예시 모음 behind
  "More tabs" (experiment, both).
- Dark mode follows the system; hard-coded #555 was hard to read (experiment by researcher; verifier did not re-test).

**P15 - CSV (used by the table plan)**
- `gr.DownloadButton(value=path)` served bytes starting `efbbbf`, `content-disposition: attachment`; file copied into the
  Gradio cache (`GRADIO_TEMP_DIR`) (experiment; `probe_misc.json`; sdk-source `routes.py` octet-stream for non-safe MIME).
- OWASP: cells starting `= + - @`, tab, CR, LF or full-width variants start formulas; quote cells, prefix `'`; Excel may
  undo it (doc: https://owasp.org/www-community/attacks/CSV_Injection).
- AI Basic Act guidance: results leaving the service carry the label themselves (3P law-firm summary:
  https://www.shinkim.com/kor/media/newsletter/3142).

### 3.3 Limits and visitors

**P16 - Visitor key**
- `gr.Request` exposes headers, client, query_params, session_hash, username, path_params (doc:
  https://www.gradio.app/docs/gradio/request). Chromium sent accept-language, user-agent, sec-ch-ua*, origin, referer.
- `gr.BrowserState`: `secret` and `storage_key` are both random per start; decryption happens in the browser with the
  secret sent to the client (sdk-source `browser_state.py`, `Index-5wzl1T9Y.js`). So both must be code constants, they
  are public, never reuse `VISITOR_SALT`, and browser_id is untrusted.
- Shared-venue collision: Chrome's reduced UA is identical within a major version and accept-language is often ko-KR, so
  HMAC(day|IP|UA|AL) merges an audience (inferred; gradio-ui verifier B9). browser_id separates them; one IP + one UA
  with rotating browser ids got 30 questions (experiment; `adversarial_limits_results.json`), hence P20.
- Plain SHA-256 of an IPv4 address is reversible by enumerating 2^32 values; HMAC with a secret prevents it (inferred;
  hf-spaces H9).
- Korea has no DST; fixed `timezone(timedelta(hours=9))` needs no tzdata; rollover tested: 4th question refused until
  `2026-09-21T00:00+09:00`, allowed at 00:00:01 (experiment; `limits_store_results.json`).

**P17 - IP rule**
- Gradio builds `uvicorn.Config` without proxy options; uvicorn defaults `proxy_headers=True`, `forwarded_allow_ips`
  from `FORWARDED_ALLOW_IPS` or "127.0.0.1,::1" (sdk-source `gradio/http_server.py` 143-151, `uvicorn/config.py` 363);
  from a trusted peer uvicorn takes the rightmost untrusted XFF entry; with "*" the first entry wins
  (sdk-source `uvicorn/middleware/proxy_headers.py`).
- Local: XFF "203.0.113.7, 198.51.100.2" from 127.0.0.1 -> `client.host=198.51.100.2`; same through the Node SSR
  proxy (it forwards XFF and UA unchanged) (experiment; `hf-spaces-verify/gradio_probe/results.txt`,
  `deps-verify/smoke/ip_headers_raw_result.txt`). Without SSR on Spaces the peer is HF's proxy, so `client.host` is
  probably a shared proxy address (inferred).
- HF docs say nothing about XFF or `FORWARDED_ALLOW_IPS` on Spaces (doc search, both verifiers). HF documents an
  `X-IP-Token` header added "to all incoming requests to Spaces" (doc:
  https://www.gradio.app/docs/python-client/using-zero-gpu-spaces). A 3-year-old community Space reads the raw
  x-forwarded-for header (3P: https://huggingface.co/spaces/radames/gradio-request-get-client-ip).
- "Last public entry" protects against private internal hops; the limits verifier warns it fails if a public proxy is
  last in the chain (every visitor would share one key). Hence the probe U1 before finalizing.

**P18 - Reserve then settle; settle in the worker; stale-ticket sweep; midnight rule**
- Admission order (prototype): in-flight per visitor <= 1 -> 10 s since last start -> visitor cap -> IP cap -> daily stop
  `visitor_spend + reserved + reserve <= 4000` -> monthly stop (experiment; `limits_store.py`).
- 13 runs x 300 KRW admitted then refused; presenter still allowed (experiment).
- Leak test: a run that never calls finish leaves the visitor `busy_visitor` 6 h later; 27 such runs hold 3,900 KRW and
  a new visitor gets `daily_stop` with 0 KRW spent (experiment; `adversarial_limits_results.json`).
- Midnight: a 900 KRW run crossing KST midnight added 0 to "today" (row written under the next day) and 900 to the
  month (experiment). Fix: attribute to the start day.
- Summary reserve per chapter (synthesis, inferred): input tokens from the precomputed table x $4/1M + 16,000 output x
  $20/1M, x 1,400: smallest chapter 5,350 -> about 478 KRW, largest 66,821 -> about 822 KRW.
- Sweep ages (synthesis): QA deadline 150 s + margin -> about 5 min; summary (600 s read timeout) -> about 20 min.

**P19 - Refund rule and under-counted failed turns**
- `loop.run_agent`: `except LLMError as exc: return LoopOutcome(None, exc.notice, forced, turns)` before
  `budget.record_turn`, so a failed turn's usage is never priced (sdk-source `assistant/loop.py`). A cut stream has no
  terminal event and therefore no usage object (sdk-source `llm_openai._stream`).
- Notice kinds (sdk-source `assistant/errors.py`): `busy`, `server_error`, `timeout`, `connection` (app_retry),
  `stream_broken` (partial), `config_error`, `bad_request`, `budget` (billing), `unknown`, `moderation_flagged`.
- Settling broken runs at max(actual, reserve) keeps the daily/monthly stops from reading low (limits verifier new
  finding 4). Whether OpenAI bills output generated before a client closes the stream is undocumented (U9).

**P20 - Per-IP KRW cap, in-flight 1, 10 s spacing**
- Researcher's per-IP cap of 30 runs admitted 30 runs from one IP with fresh browser ids (experiment); table/compare
  reserve 500-1,000 KRW, so 4-8 runs close 4,000 KRW; carrier NAT merges users (inferred; limits verifier 5).
- OpenAI recommends per-user usage limits (doc: https://developers.openai.com/api/docs/guides/rate-limits.md).

**P21 - Presenter**
- `hmac.compare_digest` avoids content-based short-circuiting but may reveal lengths (doc:
  https://docs.python.org/3/library/hmac.html); hashing both sides with sha256 first equalizes lengths.
- `gr.State` is server-side: `if block.stateful: processed_input.append(state[block._id])` (sdk-source `blocks.py`);
  a fresh session sending True got `unlocked=False`; an unlocked session sending None/False stayed unlocked; a second
  session of the same visitor stayed capped (remaining 2, 1, 0, 0) (experiment; `probe_misc.json`, verifier).
- Lockout per visitor key bypassed: 40 browser ids from one IP -> 200 password tries (experiment).
- `launch(auth=...)` would put a login in front of every visitor (inferred; gradio-ui D11).
- Presenter spend mixed into visitor total in `usage_ledger_sketch.py` (experiment; `hf-spaces-verify/ledger_recheck_output.json`).

**P22 - Monthly visitor stop (proposal)**
- Spec 1.3: public monthly LLM budget 20,000 KRW (about $14), OpenAI hard limit about $12 because enforcement is late.
  Hard limits return 429 `project_spend_limit_exceeded`, "enforcement is not instantaneous", and reset with the next
  monthly cycle unless raised (doc: https://developers.openai.com/api/docs/guides/spend-limits.md).
- The presenter uses the same public project (spec 6.1 Secrets), so a hard-limit hit blocks the live demo too.
- Tension (limits verifier 6, inferred): from about 9/19 to 9/28, a 12,600 KRW visitor month can run out after about
  3 days at the full 4,000 KRW/day. Realistic QA spend is 20-50 KRW per question (live check), so 4,000 KRW/day
  needs roughly 80-200 questions. The owner decides (README 5.2).

**P23 - safety_identifier**
- Responses API: `safety_identifier` stable, at most 64 characters, hashing recommended (doc:
  https://developers.openai.com/api/reference/resources/responses/methods/create.md).
- A blocked identifier gets "identifier blocked" on future GPT-5 requests; OpenAI cannot currently unblock it and asks
  apps to keep blocked users from starting over; repeated high-risk use triggers a warning email and can stop the org's
  GPT-5 access after about 7 days; OpenAI may delay streaming for flagged users (doc:
  https://developers.openai.com/api/docs/guides/safety-checks.md).
- Logged-out previews "can send a session ID instead" (doc:
  https://developers.openai.com/api/docs/guides/safety-best-practices.md).
- Spec 4.3 currently says "safety_identifier = 방문자 해시(64자)" while the visitor hash rotates daily (P16); hence S5.

### 3.4 Summary

**P24 - Scope: 44 main chapters**
- Inventory (experiment; `summary/chapters.json`, independent verifier recount `summary-verify/recount_output.json`
  identical): 44 main chapters; 2025 제1~7장: 248 citable pages, 225,537 chars, 144,343 tokens (x0.64), 136,919 o200k
  text tokens, 146,720 payload-B tokens, about 152,845 request input tokens.
- Largest 2023 제3장: 108 pp, 97,674 chars, 65,946 payload-B, about 66,821 input. Median between 2021 제5장 (18,510) and
  2023 제2장 (19,527). Smallest 2022 제7장: 7 pp, 4,475 payload-B, about 5,350 input.
- 부록 51-78 pp per year; 2025 부록 1 조직도 and 2025 인사말/목차 in `missing.json`; main chapters: 0 printed-page gaps,
  0 citable pages without a section, section counts equal `toc.json` level-2 counts in all 44; non-citable pages inside
  chapters are dividers/blanks (at most 166 chars per chapter) (experiment, verifier).
- Live check: all 3 QA citations were short 부록 chronology cells (doc: first-live-check.md), which is why 부록 summaries
  would be weak.

**P25 - Request shape**
- Payload B tokens over 44 chapters: 932,840 (reproduced); A (read_pages-shaped) 1,033,561 and C (plain text) 923,149
  (researcher only; not decision-relevant).
- Adapter today puts `"tools": []` and `"tool_choice": "none"` on the wire; a create call without them sends neither
  key (experiment; `summary/sdk_request_shape_check_output.json`, `summary-verify/wire_recheck_output.json` cases 1, 2).
  SDK: `tools`, `tool_choice`, `service_tier`, `prompt_cache_options` default to `omit` (sdk-source openai 3.14.0
  `resources/responses/responses.py`). The reference marks both optional and is silent on an empty array (doc: create.md).
- Explicit caching: "When no explicit breakpoints are placed, the request does not use prompt caching or create cache
  writes"; GPT-5.6 cache writes 1.25x; minimum cacheable prefix 1,024 (doc:
  https://developers.openai.com/api/docs/guides/prompt-caching.md). Implicit premium avoided: +94 KRW largest, +29
  typical, +214 all 2025, +1,360 all 44 (arithmetic, verified).
- Reasoning guide: reserve at least 25,000 tokens for reasoning and outputs; `incomplete` with `max_output_tokens` can
  occur before visible output (doc: https://developers.openai.com/api/docs/guides/reasoning.md). gpt-5.6-sol max output
  128,000, max input 922,000 (doc: https://developers.openai.com/api/docs/models/gpt-5.6-sol.md).
- `assistant/limits.py` `TOKENS_PER_CHAR = 1.0`: 2023 제3장 request 113,178 chars would exceed a 100K cap; 2024 제3장
  97,547; 2020 제4장 96,149; payload B is 0.548-0.601 tokens per payload char (experiment, verifier).
- Output estimate for the largest chapter: 27 sentences, visible about 3,413 tokens; with the live-check ratio 1.78
  reasoning per visible token about 9,476; "high" scenario 18,652 (inferred). At 32K output and the 100K input cap one
  summary can cost 1,456 KRW (1,008 at 16K); largest real chapter 1,270 KRW at the 32K ceiling (arithmetic).

**P26 - Schema, prompt, fingerprint test, section check**
- Strict subset supports `minItems`/`maxItems`, `pattern`, `minimum` (listed for number; on integer inferred), `$defs`;
  up to 5,000 properties and 10 nesting levels; output follows schema key order (doc:
  https://developers.openai.com/api/docs/guides/structured-outputs.md). Schema depth 7, 13 properties (researcher).
- Draft prompt `summary-2026-09-19`, 613 tokens, in `summary/summary_proto.py` (`SUMMARY_INSTRUCTIONS`,
  `SUMMARY_ANSWER_FORMAT`).
- Quotes spanning two numbered paragraphs: 50/50 graded `paragraph_only` / `quote_not_in_paragraph`; about 55% of numbered
  "paragraphs" in main chapters are under 30 chars (median 21-25, p75 134-155) (experiment; verifier N5).
- The schema allows 1-12 free-title sections; regrouping cannot detect merged or skipped sections (inferred, N6). A
  per-chapter schema with `minItems = maxItems = N` is possible but each new schema adds first-request latency (doc).

**P27 - Verification and when to re-verify**
- Flatten + `verify_answer` + regroup: exact 200/200, moved_page 50/50, moved_paragraph, paragraph_only, page_not_read,
  quote_too_short all graded as expected; regroup lengths correct (experiment; `verify_summary_check_output.json`,
  `verify_recheck_output.json`).
- Timing (experiment; `summary-verify/timing_recheck_output.json`, 2023 제3장): absent quote n=1 0.048-0.061 s; n=25
  0.806-1.277 s; n=54 2.845-3.367 s; schema maximum 297 citations 14.6 s. Cause: `check_citation` recomputes `keyed()`
  for every candidate paragraph (sdk-source `assistant/citations.py`). CPU Basic likely slower (inferred).

**P28 - Storage key and record**
- `summary_proto.storage_key()` appends `corpus_hash[:12]` to the path, so a changed corpus never finds the old file and
  "stale" cannot happen (sdk-source; verifier N9). Use `summaries/{year}/ch{NN}/{prompt_version}/{model}.json` with
  `corpus_hash` (sha256 of the chapter's page_ids + texts) inside the record.

**P29 - Flex pre-generation**
- Flex pricing row for gpt-5.6-sol: $2.00 input / $0.20 cached / $2.50 cache write / $10.00 output (long context
  $4 / $0.40 / $5 / $15), exactly half of standard $4 / $0.40 / $5 / $20; Batch row identical (doc:
  https://developers.openai.com/api/docs/pricing.md). `assistant/pricing.py` already halves when
  `service_tier == "flex"` (sdk-source).
- Flex "in beta with limited model availability"; capacity shortage "429 Resource Unavailable", not charged; retry with
  exponential backoff or with service_tier auto/omitted; SDK default timeout 10 min, examples 900 s
  (doc: https://developers.openai.com/api/docs/guides/flex-processing.md; sdk-source `_constants.py`
  `DEFAULT_TIMEOUT = httpx2.Timeout(timeout=600, connect=5.0)`).
- A project can disallow tiers: 400 "Invalid service_tier argument" (doc: error-codes.md). Overload: 503
  `server_is_overloaded`; "Handle both 429 and 503" (doc: rate-limits.md).
- Current retry: 429 without Retry-After -> BUSY with delays about 0.41 s and 0.95 s; 429 with `retry-after: 60` -> no
  retry (`MAX_RETRY_AFTER_S = 20.0`, `assistant/errors.py` line 68); 503 overloaded -> SERVER_ERROR, retried after about
  0.5 s and 1 s (experiment; `wire_recheck_output.json` case 4).
- Adapter parses a streamed flex completion unchanged (status completed, service_tier "flex", usage mapped) (experiment).
- Batch: 50% off, `completion_window` only `24h`, 50,000 requests / 200 MB, `batch_expired`, completed requests billed;
  `/v1/batches` and `/v1/files` retained until deleted, batch files expire after 30 days (doc: batch.md, your-data.md).
- Costs at the measured ratio (standard / flex, KRW; arithmetic verified within 2 KRW, reasoning volume unmeasured):
  typical 273 / 136; largest 640 / 320; 2025 7 chapters 1,946 / 973; all 44 12,267 / 6,134; largest at 32K ceiling
  1,270 / 635; 20,000 KRW buys 73 standard or 147 flex typical summaries (`summary/summary_costs_output.json`,
  `summary-verify/cost_recheck_output.txt`). Pre-generation runs on the development key.

**P30 - Visitor summaries; "shown" = first answer text**
- `llm_openai.turn` sets `shown=True` on every `emit`, including `thinking` (reasoning item added) and `answer_started`
  (sdk-source `assistant/llm_openai.py` lines 84-87, 129-136). Re-run: an `error` event after the reasoning item ->
  `stream_broken`, one request, no retry (experiment; verifier N2). Spec 4.3 wording is about letters on screen.
- Structured output streams as `response.output_text.delta`; the adapter ignores it today (sdk-source
  `types/responses/response_text_delta_event.py`). `response.queued` exists (sdk-source `response_queued_event.py`).
- Visitor-triggered summaries stay on the standard tier (spec 5.2); flex latency is unpublished.

**P31 - Progress events for summaries**
- `progress_proto.SummaryProgress` self-test: random 1-9 char chunks -> 6 `section_started` in order, `sentences_written`
  every 5 sentences, one `overview_started` (experiment, re-run by verifier). Filter deltas by the `item_id` of the
  non-commentary message (inferred N11; live check saw no commentary).

### 3.5 Gallery, safety, presentation

**P32 - Gallery**
- OpenAI Sharing & Publication Policy (updated 2022-11-14): manually review each generation before sharing, attribute
  the content to your name, label AI-generated content "in a way no user could reasonably miss or misunderstand"; use
  good judgment when taking audience requests (doc: https://openai.com/policies/sharing-publication-policy/).
  It is part of "OpenAI Policies" in the Services Agreement (doc: https://openai.com/policies/services-agreement/).
- Replay with network blocked and no `openai`/`httpx`/`assistant` import; item size 0.9-2.5 KB (experiment;
  `limits-store-safety/replay_prototype.py`, `replay_results.json`). Every Space commit restarts the Space (doc), so
  gallery changes must finish before the 9/27 freeze.

**P33 - MOFA links and quote length**
- `https://www.mofa.go.kr/www/brd/m_4105/view.do?seq=N` returned HTTP 200 (experiment, both): 291 "2021 외교백서"
  (2020년치, posted 2021-12-06), 292 "2021년도 국제정세와 외교활동" (2022-12-29), 298 "2022년도" (2024-01-03), 299
  "2023년도" (2024-12-31), 300 "2024년도" (2025-05-30), 301 "2025년도" (2026-07-10). Board PDF names equal
  `corpus/volumes.json` file names. seq 271 = 2018 edition, 290 = 2020 edition (chapter PDFs; fits spec 2.3).
  List page: `https://www.mofa.go.kr/www/brd/m_4105/list.do`.
- Footer "본 누리집의 모든 권리는 외교부에 귀속됩니다"; copyright policy allows free use only for KOGL Type 1 marked
  works, requires source, asks prior consultation otherwise, and cites 저작권법 제24조의2 (doc:
  https://www.mofa.go.kr/www/wpge/m_4190/contents.do). The "공공누리 인증" footer image sits inside an HTML comment;
  no KOGL mark on the six posts or in the first/last 3 pages of the six PDFs (experiment). 2021 edition credits summit
  photos to 청와대 (experiment) -> keep page images out.
- Copyright Act Art. 28 (quotation within a justified scope and fair practice), Art. 37 (source; fine up to 5 million
  KRW), amendment effective 2026-10-29 (doc:
  https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=695&ccfNo=3&cciNo=2&cnpClsNo=2). Art. 24-2 text:
  https://casenote.kr/법령/저작권법/제24조의2 (3P copy).
- No code limit on quote length; the QA prompt says usually 20-60 characters (sdk-source `assistant/prompts.py`,
  `citations.py`; limits verifier 11). 80-char display cap is a synthesis value.

**P34 - Notice, retention, logging**
- AI Basic Act and decree in force 2026-01-22; current text Act 21311 (in force 2026-07-21); Art. 2(7) 인공지능사업자
  includes individuals doing business; Art. 31(1) prior notice, 31(2) labeling; at least a year before fines promised
  (3P: https://casenote.kr/법령/인공지능_발전과_신뢰_기반_조성_등에_관한_기본법,
  https://datalaw.kr/posts/ai-basic-law-business-duties/, https://www.shinkim.com/kor/media/newsletter/3142).
- OpenAI Services Agreement (effective 2026-01-01): §2.2 Customer Applications for End Users; §3.2 responsible for all
  account activity; §3.3(c) no minors without parental or guardian consent ("minors" undefined); §16.12 End Users only in
  Supported Countries (doc). Supported countries: 208 entries including South Korea; offering access elsewhere "may
  result in your account being blocked" (doc: https://developers.openai.com/api/docs/supported-countries.md).
  Usage Policies effective 2025-10-29 (doc: https://openai.com/policies/usage-policies/).
- Korean majority is 19 (민법 제4조), so "만 19세 미만" covers both Korean law and OpenAI's under-18 guidance (doc:
  https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance.md).
- Abuse monitoring logs retained up to 30 days; API data not used for training unless the org opts in (doc:
  https://developers.openai.com/api/docs/guides/your-data.md).
- PIPA: Art. 2(1)(나), 2(5), 22-2, 28-8, 30, 58-2 cited from a 2023-09-15 copy; Act 21445 took effect 2026-09-11
  (3P: https://datalaw.kr/guides/pipa-2026-amendment/) -> recheck on law.go.kr (U12). Practical posture only, not legal advice.
- HF Content Policy effective 2025-04-10; ToS "solely responsible for the Content you post" (doc:
  https://huggingface.co/content-policy, https://huggingface.co/terms-of-service).
- Retention deletion "at startup" never runs on a Space that stays up 30+ days (limits verifier 16) -> also at KST rollover.
- Log visibility for non-owners of a Protected Space is undocumented (hf-spaces F21) -> log only run id, task, status,
  cost, elapsed.

**P35 - Presentation run-book**
- cpu-basic sleeps after 48 h and "Anyone visiting your Space will restart it automatically" (doc:
  https://huggingface.co/docs/hub/spaces-gpus); manage-spaces says cpu-basic is "automatically be paused after 48h"
  and only the owner restarts a paused Space (doc: https://huggingface.co/docs/huggingface_hub/guides/manage-spaces).
  Public API shows idle cpu-basic Spaces as SLEEPING with `gcTimeout` 172800 (experiment).
- Any change to secrets or hardware triggers a restart (doc: manage-spaces). `hf spaces hot-reload` (experimental,
  Gradio 6.1+) also creates a commit (sdk-source CLI help; hf-spaces verifier N11).
- GPT-5.6 generation may pause several seconds mid-stream while classifiers review output (doc:
  https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6.md).
- PRO billing: credit card with 3D Secure; subscriptions renew on the 1st; first month prorated (doc:
  https://huggingface.co/docs/hub/billing). PRO $9/month includes Gradio/Docker Spaces on compute, Protected, Dev Mode
  (doc: https://huggingface.co/pricing). New free accounts lost CPU Basic Gradio Spaces around 2026-07-09 (3P forum
  thread 177629). Effect of a PRO lapse undocumented.
- Local startup: `import gradio` 3.2-4.3 s warm (12.2 s cold), `import openai` 1.5-2.2 s, corpus load 0.06-0.23 s,
  first search 1-3 ms, RSS 180-200 MB (experiment; `hf-spaces/startup_probe_output*.json`, `deps/footprint_results.json`,
  `deps-verify/foot/footprint_v1.json`). BM25 latency: median 0.26-0.46 ms, p95 up to 0.66 ms.

## 4. Refuted claims and resolutions

| # | Topic | Claim | Refutation (evidence) | Resolution |
|---|---|---|---|---|
| R1 | hf-spaces | The usage-ledger sketch behaves as spec 6.3 | Presenter spend added to the visitors' daily total; no in-flight reservation: budget 100 KRW, 10 parallel grants, 900 KRW (experiment; `hf-spaces-verify/ledger_recheck_output.json`) | P18 reserve-then-settle; P21 presenter spend separate; use `limits_store.py` as the base, not the sketch |
| R2 | deps | Whole app process about 190 MB (222 MB Space-like) | Spaces enable SSR by default, adding a Node process of about 94 MB (experiment; `deps-verify/smoke/result_v1_ssr*.json`) | P12 `ssr_mode=False`; plan capacity at about 0.3 GB anyway (still under 2% of 16 GB) |
| R3 | summary | Citation check worst case 0.553 s, so re-verify on every display | 0.03-0.06 s per absent quote; 54 absent 2.8-3.4 s; schema max 297 -> 14.6 s (experiment; `timing_recheck_output.json`) | P27 store the verified answer; re-verify only when checker fingerprint or corpus_hash changes (optionally memoize `keyed()`) |
| R4 | summary | Progress regex can false-tick on a literal `"title":` inside a quote | Inner quotes are escaped in valid JSON; test gave exactly one section and one overview (experiment) | No action; still read only final-answer deltas (P31) |
| R5 | limits | "5 wrong passwords then locked for the day" protects the presenter | Per-visitor-key lockout bypassed with 40 browser ids -> 200 tries (experiment; `adversarial_limits_results.json`) | P21 long random password, per-IP-day throttle, no global lockout |
| R6 | limits | A cut stream that cost money still counts | `loop.run_agent` drops the failed turn's usage; cut or timed-out turns add 0 KRW; the researcher's test injected cost=25 by hand (sdk-source `loop.py`) | P19 count the slot and settle at max(actual, reserve) for timeout/connection/server_error/stream_broken/unknown |

## 5. Uncertain claims and resolutions

| # | Topic | Claim | Why uncertain | Resolution |
|---|---|---|---|---|
| Q1 | gradio-ui | HF docs say nothing about XFF / proxy handling | No primary HF page; `X-IP-Token` is documented for Spaces | P17 provisional rule; probe U1 on first deploy |
| Q2 | gradio-ui | Dark mode makes #555 hard to read | Not re-tested | P14 use theme CSS variables; screenshot in dark mode during T4 (U14) |
| Q3 | hf-spaces | Build timeout about 45 min (forum) | Not in official docs; only startup timeout 30 min is documented | Emulated build about 3 min 15 s without cache; record the real build time on first deploy (U13) |
| Q4 | deps | Linux RSS equals the Windows working set (about 0.2 GB) | No Linux run (Docker daemon stopped) | Read Space metrics on first deploy (U5); plan 0.3 GB |
| Q5 | deps | A foreign `python.exe app.py` listens on 127.0.0.1:7861 | Not present at verification time (transient) | Use a free port in local runs; never kill unknown processes |
| Q6 | summary | Payload token totals A 1,033,561 / C 923,149 | Only B was rebuilt | Not decision-relevant; B (932,840) chosen and reproduced |
| Q7 | summary | One output sentence with 1-2 citations is about 120 tokens | Not re-run | Cost estimates only; replace with measured usage after the first summary check (U6) |
| Q8 | summary | OpenAI returns 400 for an empty tools array (Portkey) | Page names no endpoint; openai-agents 0.22.2 sends `tools=[]` on the Responses path (sdk-source) | Moot: omit both keys when tools is empty (P25) |
| Q9 | summary | The adapter's 180 s timeout is too short for summaries | With `stream=True` it is a per-read inactivity timeout (sdk-source `_base_client.py`, `x-stainless-read-timeout`); silence that long is unknown | Raise to 600 s standard / 900 s flex for summaries (harmless); QA keeps 180 s (C14) |
| Q10 | limits | Worst-case daily-stop overshoot about 2 x 1,350 KRW | If all input were billed as cache writes, one QA run under QA_CAPS costs about $1.20 (1,680 KRW); "2 in flight" holds only with one shared concurrency_id | P13 one shared id; P18 reserves; OpenAI hard limit final guard; bound documented in 3.2 P13 |
| Q11 | limits | Replay of v1 records reproduces realistic timing | Totals equal `elapsed_s` by construction | P10 record v2 with per-event `t` |
| Q12 | limits | Give `gr.BrowserState` a fixed secret so values survive restarts | `storage_key` is also random per start; secret is sent to the browser | P16 fix both as public code constants; never reuse `VISITOR_SALT`; browser_id untrusted |
| Q13 | limits | What client.host and XFF contain on a Space | No primary doc; a web-search summary claiming HF trusts XFF had no source | U1 probe; P17 provisional rule |
| Q14 | limits | PIPA articles as cited | Copy is the 2023-09-15 version; Act 21445 effective 2026-09-11 | U12 recheck on law.go.kr; notice wording kept conservative |

## 6. Confirmed-with-caveat facts that shape the plan

- Shared `concurrency_id` takes the lowest limit lazily and permanently (C2).
- `max_size` is global across ids (C1).
- `session_hash` is client-generated and reusable (P10, P21); never log or display it.
- `api_open` differs between local (open) and Spaces (closed); set it explicitly (P13).
- Idle cpu-basic Space: "sleeping" in spaces-gpus vs "paused" in manage-spaces (P35).
- The build-order evidence is from late 2025 on `python:3.10`; no public log for a python_version 3.12 Gradio Space or
  Sep 2026 (U4). The 76-pin lock is safe either way.
- 401 from the anonymous Hub API cannot distinguish Protected from nonexistent (hf-spaces verifier F21).
- Gradio serves no files from the app folder unless allowed paths are set (P4).
- The mcp extra makes `import gradio` import mcp in a Space-like env (+0.33-1.5 s, +27 MB) (experiment; deps).
- `runner.run` builds a new OpenAI client per call when `llm` is None (0.8-4.8 ms each); the web layer can pass one
  shared `OpenAIResponses` (deps verifier 7).
- `assistant/llm_openai.load_api_key` reads `OPENAI_API_KEY` from the environment first, so a Space Secret works
  unchanged (sdk-source lines 41-43).
- Variables are publicly viewable and copied into duplicates; Secrets are unreadable after saving and not copied
  (doc: spaces-overview). Never run `hf spaces secrets add --secrets-file .env`.
- Outbound network from Spaces only on ports 80, 443, 8080 (doc: spaces-overview); OpenAI uses 443.

## 7. Spec changes: rationale (Korean wording in README section 3)

| # | Spec section | Why the spec must change | Decisions |
|---|---|---|---|
| S1 | 3.1 `store/` row | Gallery and seed summaries must survive a missing bucket; bucket semantics restrict writes to create-once files | P5, P6 |
| S2 | 3.1 `assistant.run` interface | New `should_stop` argument and `cancelled` status; per-event `t` in records | P8, P10 |
| S3 | 3.2 flow | Admission now reserves estimated cost and settles afterwards; IP and monthly layers | P18, P20, P22 |
| S4 | 4.3 retry rule | Progress lines (thinking, queued) must not block retries; spec intent is answer letters | P30 |
| S5 | 4.3 safety_identifier | Daily-rotating visitor hash conflicts with OpenAI's stable-id requirement | P23 |
| S6 | 4.3 SDK pin | Install check done; the lock must also pin the build's last-step closure | P1 |
| S7 | 4.4 summary caps | 16K output below OpenAI's 25K guidance; 1.0 token/char estimate blocks 2023 제3장; cost column rises to about 1,500 KRW | P25 |
| S8 | 5.2 summary | Scope is 44 main chapters, not "all chapters"; token figure 6.7만 with payload B; store verified answer + corpus_hash; detached generation; flex retry policy | P9, P24, P27-P29 |
| S9 | 6.1 Space | Third Secret `VISITOR_SALT`; public Variables; `python_version "3.12"`; allow-list deploy; hardened launch; corpus never in allowed paths | P2-P4, P12, P16 |
| S10 | 6.1 sleep, 9 schedule | Restart on any push or secret change; freeze on 9/27; sleep vs paused wording | P35 |
| S11 | 6.2 tab order | Only 2 tabs visible at phone width; gallery is the zero-cost fallback | P14 |
| S12 | 6.2 evidence display | Exact MOFA URLs; 80-char quote cap; escaping rule; stop button; notice required by AI Basic Act Art. 31 and OpenAI terms | P8, P11, P33, P34 |
| S13 | 6.3 layer 2 | Browser id added to the hash inputs; reserve/refund rule; per-IP KRW cap; admit caps are soft | P16, P17, P19, P20 |
| S14 | 6.3 layer 3 + cost paragraph | Reserve-then-settle; presenter spend separate; broken runs counted at max(actual, reserve) | P18, P19, P21 |
| S15 | 6.3 new layer 3-1 | Monthly visitor stop to keep presenter headroom under the $12 hard limit (owner confirmation) | P22 |
| S16 | 6.3 presenter row | Lockout replaced by throttle; long random password; 3 h per-window unlock | P21 |
| S17 | 7 failure table | New cases: stop/close, full queue, bucket down, identifier blocked, presentation watchdog | P6, P8, P9, P13, P23, P35 |
| S18 | 8.1 LLM-free tests | Escaping, 403, version equality, bundle content, prompt fingerprint, ledger edge cases | P2-P4, P11, P18, P26 |
| S19 | 11 user actions | Deadline moves to 9/18 for PRO; added login, bucket, Space, 3 secrets | README section 5 |
| S20 | 12 checklist | Mark install/Gradio/HF checks as done; notice replaces "record only" for terms | P1, P7, P12, P34 |
| S21 | 13 file layout | `deploy/`, `web/gallery/`; corpus ships in the bundle | P3, P32 |
| S22 | 5 intro (reference only) | QA cost 20-50 KRW measured vs 190-250 KRW estimate; already scheduled for correction after the gold set | - |

## Appendix A. Draft notice text (Korean, for the screen; needs owner approval)

> **이용 안내** · 이 서비스는 OpenAI의 AI 모델(gpt-5.6-sol)이 외교부 외교백서를 찾아 읽고 답을 만듭니다. 답은 틀릴 수 있으니 근거 쪽수와 외교부 원문으로 확인해 주세요.
>
> **자세히**
> - 모으는 것: 질문, 고른 연도, 답과 사용량, 방문자 구분값(IP · 브라우저 정보를 되돌릴 수 없게 바꾼 값). 원래 IP는 저장하지 않습니다.
> - 쓰는 곳: 하루 한도 계산, 오류 고치기, 남용 막기.
> - 보관: 질문 · 답 기록은 30일 뒤 삭제합니다. 질문이 없는 사용량 합계는 2026-12-31까지 보관합니다.
> - 보내는 곳: 질문은 OpenAI(미국)로 전송되며, OpenAI는 남용 감시를 위해 최대 30일 보관합니다. [조직이 데이터 공유에 동의하지 않았음을 확인한 경우에만: 학습에 쓰이지 않습니다.] 기록은 Hugging Face에 보관합니다.
> - 이름, 연락처, 주민등록번호 같은 개인정보는 쓰지 마세요.
> - 만 19세 미만은 보호자 동의 뒤 이용해 주세요.
> - 문제 신고 · 기록 삭제 요청: [연락처]
> - 개인 포트폴리오 데모이며 외교부와 관계없습니다.

## Appendix B. Source index

- PyPI JSON: https://pypi.org/pypi/gradio/json, https://pypi.org/pypi/openai/3.14.0/json, https://pypi.org/pypi/httpx2/json,
  https://pypi.org/pypi/numpy/2.5.3/json, https://pypi.org/pypi/huggingface_hub/json, https://pypi.org/pypi/uvicorn/json
- Hugging Face docs: https://huggingface.co/docs/hub/spaces-overview, /spaces-config-reference, /spaces-dependencies,
  /spaces-gpus, /spaces-storage, /spaces-embed, /spaces-dev-mode, /storage-buckets, /storage-buckets-access,
  /storage-limits, /storage-regions, /rate-limits, /billing, /repositories-getting-started;
  https://huggingface.co/docs/huggingface_hub/guides/manage-spaces, /guides/upload, /guides/buckets, /guides/cli;
  https://huggingface.co/pricing, https://huggingface.co/pro, https://huggingface.co/storage;
  https://huggingface.co/changelog/protected-spaces, https://huggingface.co/changelog/storage-buckets-for-spaces;
  https://github.com/huggingface/hf-mount; https://huggingface.co/content-policy, https://huggingface.co/terms-of-service
- Gradio docs: https://www.gradio.app/main/guides/gradio-6-migration-guide, https://www.gradio.app/guides/environment-variables,
  https://www.gradio.app/docs/gradio/html, https://www.gradio.app/docs/gradio/request, https://www.gradio.app/docs/gradio/chatbot,
  https://www.gradio.app/guides/resource-cleanup, https://www.gradio.app/guides/file-access,
  https://www.gradio.app/guides/setting-up-a-demo-for-maximum-performance, https://www.gradio.app/guides/agents-and-tool-usage,
  https://www.gradio.app/docs/python-client/using-zero-gpu-spaces
- OpenAI docs (developers.openai.com/api/docs/...): pricing.md, guides/flex-processing.md, guides/batch.md, guides/reasoning.md,
  guides/structured-outputs.md, guides/prompt-caching.md, guides/error-codes.md, guides/rate-limits.md, guides/background.md,
  guides/streaming-responses.md, guides/your-data.md, guides/spend-limits.md, guides/safety-best-practices.md,
  guides/safety-checks.md, guides/safety-checks/under-18-api-guidance.md, guides/agent-builder-safety.md,
  guides/latest-model/gpt-5.6.md, models/gpt-5.6-sol.md, supported-countries.md;
  https://developers.openai.com/api/reference/resources/responses/methods/create.md
- OpenAI policies: https://openai.com/policies/usage-policies/, https://openai.com/policies/services-agreement/,
  https://openai.com/policies/sharing-publication-policy/
- Python: https://docs.python.org/3/library/hmac.html
- Security: https://owasp.org/www-community/attacks/CSV_Injection
- Korean law and MOFA: https://www.mofa.go.kr/www/brd/m_4105/list.do, https://www.mofa.go.kr/www/wpge/m_4190/contents.do,
  https://easylaw.go.kr/CSP/CnpClsMain.laf?popMenu=ov&csmSeq=695&ccfNo=3&cciNo=2&cnpClsNo=2,
  https://casenote.kr/법령/저작권법/제24조의2, https://casenote.kr/법령/인공지능_발전과_신뢰_기반_조성_등에_관한_기본법,
  https://www.shinkim.com/kor/media/newsletter/3142, https://datalaw.kr/posts/ai-basic-law-business-duties/,
  https://datalaw.kr/guides/pipa-2026-amendment/ (3P)
- Third-party / forum: https://discuss.huggingface.co/t/gertie01-hub-6oa42x9a-report/170468,
  https://discuss.huggingface.co/t/report-not-working/171762,
  https://discuss.huggingface.co/t/new-free-accounts-cannot-create-cpu-basic-gradio-spaces-only-zerogpu-available/177629,
  https://huggingface.co/spaces/agents-course/First_agent_template/discussions/251,
  https://huggingface.co/spaces/davanstrien/bucket-sqlite-probe-gradio, https://huggingface.co/spaces/davanstrien/bucket-sqlite-probe-docker,
  https://huggingface.co/spaces/radames/gradio-request-get-client-ip,
  https://raw.githubusercontent.com/gradio-app/trackio/main/trackio/sqlite_storage.py,
  https://portkey.ai/error-library/input-validation-error-10476, https://cborg.lbl.gov/flex_processing/,
  https://github.com/gradio-app/gradio/issues/3114
- Verifier notes: `gradio-ui-verify/verify.md`, `hf-spaces-verify/verify.md`, `deps-verify/verify.md`,
  `summary-verify/verify.md`, `limits-store-safety-verify/verify.md`
