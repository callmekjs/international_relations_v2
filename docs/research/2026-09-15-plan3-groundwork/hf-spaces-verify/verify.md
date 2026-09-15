# Verification: Plan 3 groundwork, topic hf-spaces (2026-09-15)

Adversarial re-check of `plan3/hf-spaces` (researcher summary + files). Repository only read (git status clean before and after).
No Hugging Face account action, no OpenAI call. Web: official HF/Gradio/OpenAI docs, PyPI JSON, public Space API/raw files, forum threads (labelled).

## 주석님용 한 줄 요약

| 결론 | 내용 |
|---|---|
| 조사 결과는 대부분 맞음 | PRO 필요, 사양, 48시간 잠들기, Protected, 비밀값, 저장 방식, 요금, Python 3.12 필수 모두 공식 문서나 재실험으로 확인 |
| 놓친 것 1 | Hugging Face에서는 Gradio 화면이 기본으로 "SSR" 방식(앞에 Node 프로그램이 하나 더 붙음)으로 돈다. PC에서 시험한 방식과 다르다. 앱에서 이 기능을 끄는 것을 권함 |
| 놓친 것 2 | 방문자 IP를 읽는 방법이 이 설정에 따라 달라진다. 방문자 한도는 브라우저를 바꾸면 피할 수 있는 "약한 한도"이고, 진짜 방어는 하루 전체 한도와 OpenAI 강제 한도다 |
| 놓친 것 3 | 예시 모음과 미리 만든 요약은 저장소(Bucket)가 아니라 Space 코드와 함께 올리는 편이 안전하다. 저장소 연결이 고장 나도 발표 볼거리가 남는다 |
| 놓친 것 4 | 시제품 코드에서 발표용 비밀번호로 쓴 요금이 "방문자 하루 합계"에 섞여, 발표 날 방문자가 일찍 막힐 수 있다 |
| 요금 | PRO는 매달 1일 결제, 첫 달은 날짜만큼 나눠 청구. 카드는 3D Secure 지원 필요 |

## 1. Verdicts per claim

Legend: C = confirmed, R = refuted, U = uncertain. Kind of evidence in brackets.

| # | Claim (researcher) | Verdict | Evidence |
|---|---|---|---|
| F1 | Gradio/Docker Spaces need a paid plan to create (PRO for personal); Static free; free accounts max 2 Gradio Spaces on ZeroGPU | C [doc] | spaces-overview warning: "Gradio and Docker Spaces run on compute and require a paid plan to create". Free: "up to 2 Gradio Spaces running on ZeroGPU" ("in good standing") |
| F2 | PRO $9/month incl. Gradio & Docker Spaces, Dev Mode; Protected is PRO | C [doc] | pricing: "$9 /month", "Host ZeroGPU, Gradio & Docker Spaces", "Spaces Dev Mode"; spaces-overview: "Protected visibility is part of PRO or Team & Enterprise plans" |
| F3 | Free CPU Basic restriction reported 2026-07-09; PRO-lapse effect undocumented | C [forum] / U | Forum thread 177629 first post 2026-07-09; no staff answer. billing doc silent on lapse |
| F4 | README keys and defaults (python_version 3.10, startup_duration_timeout 30 min, disable_embedding false) | C [doc] | spaces-config-reference |
| F5 | suggested_storage ignored; preload_from_hub no private repos | C [doc] | "The persistent storage feature is no longer available"; "Preloading of private repos is not supported yet" |
| F6 | Preinstalled huggingface_hub, requests, datasets, gradio; requirements/pre-requirements/packages.txt | C [doc] | spaces-dependencies |
| F7 | numpy 2.5.3 needs Python >= 3.12; set fails on 3.10, resolves on 3.12 (71 pkgs, httpx 0.28.1 + httpx2 2.13.0) | C [experiment re-run] | PyPI requires_python ">=3.12"; `uv pip compile` x86_64-manylinux_2_28: 3.10 exit 1, 3.12 exit 0 (71), 3.13 exit 0; also resolves with `gradio[oauth,mcp]==6.27.0 spaces uvicorn websockets` (pydantic drops to 2.12.5 because the mcp extra pins `<=2.12.5`) |
| F8 | Every push rebuilds/restarts; secret or hardware change restarts | C [doc] | spaces-overview "automatically rebuild and restart"; manage-spaces "Any change in your Space configuration (secrets or hardware) will trigger a restart" |
| F9 | `hf spaces logs --build/-f/-n`, `restart --factory-reboot`, `wait`; SSE log endpoints need auth | C [sdk-source + doc] | hf 1.31.0 `--help` output; spaces-gpus streaming section |
| F10 | SPACE_ID/SPACE_HOST/CPU_CORES/MEMORY; api_open False when SYSTEM=spaces | C [doc + sdk-source] | spaces-overview built-in env vars; gradio blocks.py:1178 `api_open = utils.get_space() is None`, utils.py:603 |
| F11 | Build timeout undocumented (~45 min forum); startup timeout 30 min | U (build) / C (startup) | Build value not found in docs; startup default in config reference |
| F12 | CPU Basic 2 vCPU/16 GB/50 GB free; CPU Upgrade 8 vCPU/32 GB $0.03/h | C [doc] | spaces-gpus table |
| F13 | cpu-basic sleeps after 48 h; visitor wakes; custom sleep time needs paid hardware | C [doc + sdk-source] with caveat | spaces-gpus "currently, 48 hours", "Anyone visiting your Space will restart it automatically". Caveat: manage-spaces says cpu-basic is "automatically be paused after 48h" (a paused Space needs the owner). Public API shows idle cpu-basic Spaces as stage SLEEPING, which supports "sleep". hf_api warns (does not raise) on sleep_time with cpu-basic |
| F14 | Public API gcTimeout 172800, region "us" | C [experiment re-run] | gradio-templates/chatbot: RUNNING, cpu-basic, gcTimeout 172800, region us; davanstrien probe: SLEEPING, gcTimeout 172800, region us, bucket volume at /data readOnly false |
| F15 | Only owner restarts a paused Space; paused not billed | C [doc] | spaces-gpus pause section |
| F16 | Startup: import gradio 3.2 s warm, RSS about 200 MB, corpus 0.18-0.23 s | C [experiment re-run] | re-run: gradio 3.99 s, openai 2.22 s, corpus 0.19 s, first search 1 ms, RSS 179.6 MB. Not measured: SSR Node process (+~85 MB locally), see N1 |
| F17-F18 | Protected: code private, app public at hf.space and custom domain, not clonable; Private gives 404 | C [doc] | spaces-overview table; changelog 2026-03-20 "private on Hugging Face while still keeping their URL publicly accessible" |
| F19 | Embedding needs public or protected | C [doc] | spaces-embed |
| F20 | Variables public and duplicated; Secrets unreadable, not duplicated | C [doc] | spaces-overview managing secrets |
| F21 | Unknowns on Protected (page, logs, wake); anonymous API 401 for non-public id | C (unknowns remain) / 401 is uninformative | A nonexistent id also returns 401 to anonymous API and page requests (re-run), so 401 cannot tell protected from missing. Changelog wording suggests the huggingface.co Space page is private to others [inferred] |
| F22 | Secrets and Variables arrive as env vars in Gradio Spaces | C [doc] | "both are exposed to your app as environment variables" |
| F23 | `hf spaces secrets add -s / --secrets-file`, `variables add -e` | C [sdk-source] | CLI help 1.31.0 |
| F24 | load_api_key reads env first | C [repo] | assistant/llm_openai.py:41-43 |
| F25 | Ephemeral disk; buckets as volumes recommended | C [doc] | spaces-storage |
| F26 | Buckets Xet-backed, non-versioned, mutable; create/sync/--delete/--dry-run; deletes permanent | C [doc] | storage-buckets |
| F27 | Attach via settings, Volume API, `set_space_volumes` replaces all, CLI `-v hf://buckets/u/b:/data[:ro]`, `hf repos create -v` | C [doc + sdk-source] | manage-spaces; `_space_api.py` Volume fields type/source/mount_path/revision/read_only/path; CLI help |
| F28 | hf-mount streaming append-only upload on close; advanced 2 s/30 s; locks single mount; 10 s staleness; last writer wins; Spaces mode undocumented | C [doc: hf-mount README] / U (Spaces mode) | hf-mount README; storage-buckets-access page has no write-mode details for Spaces |
| F29 | Third-party probe: Gradio SDK uid 0, FUSE idmapped user_id=0, SQLite + flock OK; Docker uid 1000 fails | C [third-party experiment, gradio 5.49.0, 2026-04-08] | refs/probe_gradio_README.md, probe_README.md; not re-runnable without an account |
| F30 | trackio on Spaces: journal DELETE, locking EXCLUSIVE, in-process lock because file locks unreliable | C [sdk-source] | trackio sqlite_storage.py lines 90-118, 170-178 |
| F31 | Buckets count toward storage; PRO 1 TB private then $18/TB; egress/CDN included | C [doc] | storage-limits table; storage page "Egress and CDN are included" (qualified "up to a generous 8:1 ratio") |
| F32 | CommitScheduler append-only, >= 5 min, silent retry, token; git repo not a database; commit limits undocumented; PRO 2,500/12,000/400 per 5 min | C [doc] | upload guide; storage-limits; rate-limits ("September '25" table) |
| F33-F34 | git-xet for > 10 MB; hf CLI handles large files; hf upload resumable, auto-split, --include/--exclude/--delete | C [doc + sdk-source] | repositories-getting-started; upload guide; CLI help |
| F35 | Root .gitignore used, fallback to Hub's; enforced server-side; DEFAULT_IGNORE_PATTERNS only .git and .cache/huggingface | C [doc + sdk-source] | upload guide "only a .gitignore file present at the root"; `_upload_pipeline.py:378-383`, `utils/_paths.py:25-33` |
| F36 | Repo .gitignore excludes corpus/, data/, .env, /runs/ | C [repo] | C:/international_relations/.gitignore |
| F37 | Allow-list bundle 27 files, 15,980,226 bytes; only problem missing app.py | C [experiment re-run] | real_repo_dryrun_rerun.json identical |
| F38 | < 100 files/commit (not for CLI), < 10k/folder, 60 s HTTP commit timeout | C [doc] | storage-limits |
| F39 | PRO personal Space runs in US | C [doc, inferred step] | storage-regions "For non-Team or Enterprise users, repositories are always stored in the US" + "Both Spaces's storage and runtime use the chosen region"; API region "us" |
| F40 | Outbound ports 80, 443, 8080 only | C [doc] | spaces-overview networking |
| F41 | OpenAI supports USA and South Korea; offering access elsewhere may block account | C [doc] | supported-countries page |
| Q1 | Gradio default_concurrency_limit 1, queue max_size None | C [sdk-source + runtime] | blocks.py:2678-2708; local launch printed `max_size: None default_concurrency_limit: 1` |
| Q2 | SSE heartbeat 15 s | C [sdk-source] | routes.py:459-480 |
| Q3 | Replicas only on paid hardware | C [doc] | spaces-gpus replicas note |
| Q4 | Dev Mode PRO; Gradio requirements not auto-installed; changes discarded on sleep | C [doc] | spaces-dev-mode |
| Q5 | `hf auth login` is a browser flow (URL + code) | C [sdk-source] | cli/auth.py uses OAuth device code (`request_device_code`, `verification_uri_complete`) |
| L1 | Ledger sketch: exact caps under parallel calls, rebuild after restart | C [experiment re-run, extended] | 50 parallel -> 3 granted; after restart (budget not reached) same visitor qa -> `visitor_cap` (the researcher's own test had masked this with the budget) |
| L2 | Ledger sketch behaves per spec 6.3 | R (two gaps) | presenter spend is added to the visitors' daily total (spec: "방문자 사용 합계"); in-flight overshoot: budget 100, 10 reservations -> 900 KRW (H8 is right but not in the sketch) |

## 2. Experiments re-run (files in this folder)

| Experiment | Result | File |
|---|---|---|
| Linux resolution 3.10 / 3.12 / 3.13, plus Spaces-like extras | 3.10 fails on numpy 2.5.3; 3.12 = 71 pkgs; 3.13 ok; full extras ok | deps/*.log, deps/lock*.txt |
| Local install gradio 6.27.0 + hub 1.31.0 + openai 3.14.0 + bm25s + numpy | `uv pip check`: 57 packages compatible | venv/ (259 MB, deletable) |
| Startup probe on the real corpus | RSS 179.6 MB, corpus 0.19 s | startup_probe_rerun.json |
| Bundle dry run on the real repo | 27 files, 15,980,226 bytes | real_repo_dryrun_rerun.json |
| Gradio file serving and client IP, CSR and SSR | cwd files 403; client.host = rightmost XFF when peer is 127.0.0.1 | gradio_probe/results.txt |
| Ledger edge cases | see L1, L2 | ledger_recheck.py, ledger_recheck_output.json |
| `git check-ignore --no-index` for a `dist/space` bundle inside the repo | corpus copy ignored (pattern `corpus/` matches any depth); README.md, app.py, assistant/*.py, requirements.txt NOT ignored | (command output only) |

## 3. New findings (missed or under-weighted)

N1. **SSR is ON by default on Spaces.** Gradio env-var guide: GRADIO_SSR_MODE default "False" "except on Hugging Face Spaces", where it is True. gradio 6.27.0 `_resolve_ssr_mode` reads that env when `ssr_mode=None`; in production SSR "Node will be the front proxy on the user-facing port and Python will be on an internal port behind it" (blocks.py ~3058). Local dev (no env) runs CSR, so local tests and the Space differ: an extra Node hop for every request and SSE stream, +~85 MB (local measurement), a startup-order path that code comments say produced 502s on Spaces before a fix, and a "degraded" fallback. [doc + sdk-source + experiment]

N2. **Visitor IP depends on that mode.** uvicorn trusts X-Forwarded-For only from FORWARDED_ALLOW_IPS (default 127.0.0.1,::1) and then takes the rightmost entry (uvicorn config.py:363; experiment). With SSR the Python peer is the local Node proxy, so `request.client.host` = rightmost XFF as received; with `ssr_mode=False` the peer is the HF proxy, so client.host is probably one shared proxy address. The leftmost XFF entry is client-controlled (spoofable). Per-visitor caps are soft anyway (new User-Agent = new visitor; the Gradio API is scriptable), so the global daily stop (layer 3) and the OpenAI hard limit (layer 1) are the real guards. [sdk-source + experiment; HF proxy behaviour itself not verified]

N3. **Corpus stays private at the HTTP layer too.** Gradio 6.27.0 serves only allowed/created/temp paths (`utils.is_allowed_file`); `/gradio_api/file=corpus/pages.jsonl`, `app.py`, a fake `.env` all return 403, also via the SSR proxy (SSR returns the HTML shell for other paths). This holds only if the app never adds `allowed_paths`/`GRADIO_ALLOWED_PATHS`/`gr.set_static_paths` covering the app folder or corpus. Strengthens H4 with a condition. [experiment + sdk-source]

N4. **Presentation fallback depends on the bucket in H5.** H5 puts `gallery/` and `seed/` (pre-generated summaries) on the bucket. If the mount is missing or read-only (H7 degraded mode), the zero-cost gallery (spec 6.3 layer 4) and saved summaries disappear exactly when needed. They are small, write-once, and prepared before the freeze, so they can ship in the Protected Space repo (read-only) with the bucket used only for runtime writes. [inferred]

N5. **Presenter spend is mixed into the visitors' budget** in the ledger sketch (see L2). On presentation day a few presenter summaries/tables could exhaust the 4,000 KRW visitor stop early. Spec 6.3 counts the visitors' total. [experiment]

N6. **Self-check can block startup.** `store_selfcheck.run_selfcheck` runs FUSE operations (SQLite, fsync, flock, rename) synchronously with no overall timeout; a hung FUSE call before `launch()` would delay or break startup (startup health timeout 30 min). Run it in a daemon thread after launch with a time limit. [inferred from code]

N7. **Bundle folder location.** Building `dist/space` inside the repo leaves app.py, assistant/*.py, README.md, requirements.txt untracked but not ignored (corpus copy is ignored), so a later `git add .` would push a duplicate tree to the public GitHub repo. Build into a temp/scratch folder or add `/dist/` to .gitignore. `hf upload` also never removes files deleted locally (stale files stay on the Space) unless `--delete` patterns are passed. [experiment + doc]

N8. **Sleep vs pause wording conflict** (F13 caveat). If on 9/27 the Space shows "Paused" instead of "Sleeping", only the owner can restart it; the warm-up check must be done by the user logged in, not only in a private window. [doc]

N9. **Billing details for the user checklist.** PRO: credit card only; card must support 3D-secure; "All subscriptions renew on the 1st of each month", first month prorated. So a 9/18 sign-up is charged a partial September, then $9 on 10/1. [doc: billing]

N10. **Long requests.** Old Gradio 3 era reports (gradio issue 3114, forum 24733) show 504 after about 60 s for non-queued REST calls to Spaces. Keep all LLM events on the queue (never `queue=False`, no custom FastAPI long POST routes). Multi-minute SSE on today's proxy is still unverified; keep checklist step 15. [issue/forum, old]

N11. **Minor.** Gradio telemetry defaults on (launch/error topics to api.gradio.app; analytics.py); set `GRADIO_ANALYTICS_ENABLED=False` as a Variable for tidiness. `hf spaces hot-reload` (experimental, Gradio 6.1+) exists and also creates a commit: exclude it from the freeze rules explicitly. Key-scan regex `sk-...{20,}` has no left word boundary (false positives possible on words like "task-..."); real repo currently has 0 hits. `short_description` is 39 characters. The pricing page expresses PRO private storage as "10x"; storage-limits gives the 1 TB number.

## 4. Corrected decisions (only where a decision should change)

- **H1/H11 addendum: set `ssr_mode=False` in `demo.launch()`** (or the Variable `GRADIO_SSR_MODE=False`). Why: Spaces turn SSR on by default (N1); CSR keeps local tests and the Space identical, removes the Node hop from long SSE streams and the extra process, and makes client-IP handling predictable. Re-test on the first deploy.
- **H9 addendum: derive the visitor IP from the rightmost X-Forwarded-For entry (fallback `request.client.host`), never the leftmost; log only booleans on first deploy (XFF present, number of entries, whether client.host equals the rightmost entry, private/public).** Why: N2. Also record in docs that visitor caps are soft and layers 1 and 3 are the real cost guards.
- **H5 change: ship `gallery/` and pre-generated summaries (`seed`) inside the Space bundle (read-only, Protected repo); use the bucket only for runtime writes (`usage/`, `runs/`, new visitor summaries). Lookup order for a summary: bucket, then bundled seed.** Why: N4; keeps spec 6.3 layer 4 and saved summaries alive in degraded mode; removes the `hf buckets sync` seed step from the critical path.
- **H6/H8 addendum: presenter runs are recorded (file with `presenter: true`) but not added to the visitors' daily total; the daily stop compares visitors' spend plus in-flight visitor reservations.** Why: N5 and L2; spec 6.3 layer 3 is the visitors' total.
- **H7 change: run the self-check in a background thread after `launch()` with a hard time limit (for example 60 s) and treat a timeout as degraded mode.** Why: N6.
- **H3 addendum: build the bundle outside the repo (scratch/temp) or add `/dist/` to .gitignore; add a left boundary to the key regex; decide whether to pass `--delete` patterns for `assistant/*`, `corpus/*`, `web/*`, `store/*` so removed files do not linger.** Why: N7, N11.
- **H4 condition: never set `allowed_paths`, `GRADIO_ALLOWED_PATHS` or `gr.set_static_paths` to the app root or corpus; add a no-LLM test that `/gradio_api/file=corpus/pages.jsonl` returns 403.** Why: N3.
- **H13 addendum: on 9/27 the user checks the Space status while logged in (Running / Sleeping / Paused) and restarts it from Settings if Paused; exclude `hf spaces hot-reload` during the freeze.** Why: N8, N11.

## 5. Still uncertain

Build timeout; Spaces bucket mount write mode; what closed-but-unflushed writes survive; logs visibility for non-owners; whether an anonymous visitor wakes a sleeping Protected Space; HF proxy XFF format and FORWARDED_ALLOW_IPS on Spaces; max SSE duration on hf.space; which Gradio extras the Spaces builder installs; PRO-lapse effect; VAT/overseas fee on a Korean card.

## 6. Sources

- https://huggingface.co/docs/hub/spaces-overview
- https://huggingface.co/docs/hub/spaces-config-reference
- https://huggingface.co/docs/hub/spaces-gpus
- https://huggingface.co/docs/hub/spaces-storage
- https://huggingface.co/docs/hub/spaces-dependencies
- https://huggingface.co/docs/hub/spaces-sdks-gradio
- https://huggingface.co/docs/hub/spaces-embed
- https://huggingface.co/docs/hub/spaces-dev-mode
- https://huggingface.co/docs/hub/storage-buckets
- https://huggingface.co/docs/hub/storage-buckets-access
- https://huggingface.co/docs/hub/storage-limits
- https://huggingface.co/docs/hub/storage-regions
- https://huggingface.co/docs/hub/rate-limits
- https://huggingface.co/docs/hub/billing
- https://huggingface.co/docs/hub/repositories-getting-started
- https://huggingface.co/docs/huggingface_hub/guides/manage-spaces
- https://huggingface.co/docs/huggingface_hub/guides/upload
- https://huggingface.co/pricing ; https://huggingface.co/storage
- https://huggingface.co/changelog/protected-spaces ; https://huggingface.co/changelog/storage-buckets-for-spaces
- https://github.com/huggingface/hf-mount
- https://www.gradio.app/guides/environment-variables
- https://developers.openai.com/api/docs/supported-countries
- https://discuss.huggingface.co/t/new-free-accounts-cannot-create-cpu-basic-gradio-spaces-only-zerogpu-available/177629 (forum)
- https://github.com/gradio-app/gradio/issues/3114 (issue, old)
- https://huggingface.co/api/spaces/gradio-templates/chatbot ; https://huggingface.co/api/spaces/davanstrien/bucket-sqlite-probe-gradio ; https://huggingface.co/spaces/radames/gradio-request-get-client-ip (public)
- PyPI JSON: gradio 6.27.0 (2026-09-11), huggingface_hub 1.31.0 (2026-09-10), numpy 2.5.3 (requires >=3.12), openai 3.14.0, httpx2 2.13.0, bm25s 0.3.11, hf-xet 1.6.0, gradio-client 2.7.0, spaces 0.51.3
- sdk-source (installed in venv/): gradio 6.27.0 blocks.py, utils.py, routes.py, http_server.py, analytics.py, templates/node/build/proxy_routes.js; uvicorn 0.53.0 config.py; huggingface_hub 1.31.0 _upload_pipeline.py, _commit_api.py, utils/_paths.py, _space_api.py, hf_api.py, cli/auth.py
