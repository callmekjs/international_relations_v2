# Plan 3 groundwork: deps topic, adversarial verification (2026-09-15)

Scope: re-check the "deps" research (install compatibility and app footprint). Repo read only
(`git status --porcelain` empty before and after). No OpenAI calls (fake key, base_url
`https://mock.invalid/v1`, OPENAI_API_KEY removed from child envs), .env never opened, no HF account action.
All files below are in `scratchpad/plan3/deps-verify/`.

## 1. What I re-ran

| # | Experiment | Files | Result |
|---|---|---|---|
| E1 | Fresh venv from CPython 3.12.10, `pip install gradio openai==3.14.0 bm25s==0.3.11 numpy==2.5.3 pytest` | v1/, v1_install_log.txt, v1_freeze.txt | exit 0, 0 conflict/backtrack lines, `pip check` clean, 60 packages, freeze **identical** to researcher's freeze.txt; no websockets |
| E2 | File ownership check | file_collisions_verify.txt | 0 files owned by 2 distributions; httpx/httpx2/httpcore/httpcore2 separate top-level dirs |
| E3 | PyPI JSON metadata for gradio, openai, httpx2, numpy, datasets, spaces, mcp, pydantic, bm25s, hf-gradio | pypi_check.py, pypi_reqs.py, pypi_latest.json | all version numbers, upload dates, Requires-Python and Requires-Dist lines quoted by the researcher match |
| E4 | Own smoke app (smoke/server.py, drive.py): httpx+httpx2+openai+gradio in one process, fake OpenAI client, generator handler fed by a worker thread, launched on a free 127.0.0.1 port, called with gradio_client | smoke/result_*.json | GET / 200, /config version 6.27.0, 6 streamed updates, `_client` MRO base = httpx2.Client; first 200 after 8.1 s warm (12.2 s first cold) |
| E5 | Same with `ssr_mode=True` (local Node v24.18.0) x3 | smoke/result_v1_ssr*.json | works, 6 streamed updates, **plus a node.exe child of ~94 MB working set** (Python 163-164 MB) |
| E6 | Visitor headers through Gradio with/without SSR (raw HTTP `/gradio_api/call/...` and gradio_client) | smoke/ip_headers_raw_result.txt, ip_headers_result.txt | Node SSR proxy forwards User-Agent and X-Forwarded-For unchanged; `request.client.host` is taken from X-Forwarded-For because uvicorn trusts peer 127.0.0.1 |
| E7 | Tracked code copied with `git ls-files` + tar; fast suite in v1 | copy_noprep/, copy_prep/, pytest_noprep.txt, pytest_prep.txt | without prep/: conftest ImportError (`No module named 'prep'`); with prep/: **174 passed, 9 skipped, 2 deselected** (same 9 skip reasons) |
| E8 | Fresh venv from the proposed `requirements-space.txt` + pytest | v2/, v2_install_log.txt, pytest_lock_v2.txt | installs exactly the 55 pins (+colorama, tzdata on Windows +pytest deps), `pip check` clean, **174 passed, 9 skipped** on pydantic 2.12.5 |
| E9 | Footprint, fresh process per mode, 3 reps, medians, real corpus read-only, sha256+mtime snapshot | foot/step.py, foot/run.py, foot/footprint_v1.json | see section 3; corpus unchanged = True |
| E10 | Search latency, 42 fixture queries x3 | foot/lat.py, foot/latency.txt | sub-millisecond (numbers in section 3) |
| E11 | `uv pip compile` (uv 0.9.27) for Linux x86_64 manylinux_2_28, CPython 3.12 | uv_checks.txt, lockA.txt, lockB.txt | lock recompiles to itself (diff empty); union with gradio[oauth,mcp]==6.27.0, uvicorn, spaces, datasets changes 0 pins; `gradio[mcp]==6.27.0` + `pydantic==2.13.5` is unsatisfiable; py3.11 fails on numpy, py3.13 resolves |
| E12 | Extended lock (proposed lock + build-step-4 closure, 76 pins) and emulated Space build (datasets -> -r requirements -> `gradio[oauth,mcp]==6.27.0 uvicorn>=0.14.0 spaces`) | requirements-space-with-step4.txt, v3/, v3_emul_log.txt | step 3 no resolver ERROR, **step 4 installs nothing** (freeze diff empty), `pip check` clean |

## 2. Primary-source checks

- PyPI JSON (fetched today): gradio 6.27.0 latest, 2026-09-11T03:01Z, `>=3.10`; openai 3.14.0 latest, 2026-09-14T23:29Z;
  httpx2 2.13.0, 2026-09-14T14:18Z; numpy 2.5.3 `>=3.12`, cp312 manylinux_2_27/2_28 x86_64 wheel; pydantic latest 2.13.5
  (2.14.0b2 pre-release); mcp latest 2.2.0 but gradio caps `mcp<2.0.0`, and **mcp 1.x still ships (1.30.0 on 2026-09-07)**.
- https://huggingface.co/docs/hub/spaces-config-reference : python_version "Defaults to `3.10`"; sdk_version "Specify the version of Gradio to use".
  Also: `suggested_storage` note says "persistent storage feature is no longer available".
- https://huggingface.co/docs/hub/spaces-dependencies : preinstalled huggingface_hub, requests, datasets, gradio; requirements.txt,
  pre-requirements.txt, packages.txt. No install order is documented.
- Build order evidence: https://discuss.huggingface.co/t/gertie01-hub-6oa42x9a-report/170468 (2025-11-14) shows
  `FROM python:3.10`, pip -U + `datasets "huggingface-hub>=0.30"...` (line truncated), apt, Node.js setup_20.x,
  `pip install -r requirements.txt`, then `pip install --no-cache-dir gradio[oauth,mcp]==5.49.1 "uvicorn>=0.14.0" spaces`.
  https://discuss.huggingface.co/t/report-not-working/171762 shows the same first steps on 2025-12-19.
  https://huggingface.co/spaces/agents-course/First_agent_template/discussions/251 (2025-03) shows the older `gradio[oauth]==...` step.
  No public log found for a python_version 3.12 Gradio Space or for Sep 2026.
- https://huggingface.co/docs/hub/spaces-gpus and spaces-overview: CPU Basic 2 vCPU / 16 GB / 50 GB, free; paid plan needed to create
  Gradio Spaces; cpu-basic sleeps after 48 h; outbound ports 80, 443, 8080; Protected = PRO/Team/Enterprise, source private, app public;
  secrets and variables are env vars; **variables are "publicly accessible and viewable"**.
- https://huggingface.co/docs/hub/spaces-storage : buckets attach as volumes at a mount path, read-write default. No extra Python package needed to
  read/write a mounted path, so the Storage Bucket decision adds no dependency.
- https://www.gradio.app/guides/environment-variables : GRADIO_SSR_MODE default "False" except on Spaces where it is set to True;
  GRADIO_ANALYTICS_ENABLED default "True". Source: gradio/analytics.py line 46, blocks.py `_resolve_ssr_mode`, SSR needs Node 20+.
- httpx2/_config.py `create_ssl_context`: truststore.SSLContext unless SSL_CERT_FILE / SSL_CERT_DIR.
- uvicorn/config.py: `FORWARDED_ALLOW_IPS` default "127.0.0.1,::1"; gradio has no own X-Forwarded-For handling (only the Node SSR handler).
- gradio blocks.py: `default_concurrency_limit` "Defaults to 1" (env GRADIO_DEFAULT_CONCURRENCY_LIMIT).

## 3. Footprint numbers I measured (Windows working set, medians of 3)

| Step (mode full) | s | WS MB | private MB |
|---|---|---|---|
| bare | 0 | 16.7 | 7.8 |
| import assistant.corpus | 0.58 | 39.6 | 765.6 |
| Corpus load | 0.063 | 67.3 | 792.5 |
| 2 searches + read_pages + get_toc | 0.001 | 67.5 | 792.5 |
| import gradio | 4.30 | 154.6 | 867.2 |
| import openai + OpenAIResponses(fake client) | 1.78 | 178.9 | 892.5 |
| build Blocks, 5 tabs | 0.31 | 184.0 | 897.1 |
| launch (ssr off) + GET / | 0.85 | 190.6 | 903.2 |

- corpus-only 67.5 MB; gradio+openai without corpus 162.7 MB; OPENBLAS_NUM_THREADS=1: private after numpy 26.6 MB (vs 765.6), WS unchanged.
- corpus/: 10 files, 15,897,302 bytes; corpus load 0.063-0.083 s; snapshot unchanged.
- New OpenAI client construction after import: 0.8-4.8 ms each (runner.run builds one per run when llm is None).
- SSR on: +node.exe ~94 MB WS (three runs 94.0-94.3 MB). Whole app with SSR on Spaces is therefore roughly 0.28-0.32 GB, not 0.19-0.22 GB. Still under 2% of 16 GB.
- Latency (question text): all years median 0.31 ms p95 0.47; one year 0.26/0.38; six years 0.28/0.41. Keyword strings: median 0.35-0.46, p95 up to 0.66 ms.
- site-packages: v1 326 MB, lock-only v2 327 MB, emul_B 474 MB, project .venv 171 MB.

## 4. Verdicts on researcher claims

Confirmed: versions/metadata (gradio, openai, httpx2, numpy, datasets, spaces, mcp), resolver outcome and exact freeze, no file collisions,
OpenAI client on httpx2.Client, one-process serving with streaming, conftest->prep dependency, 174/9/2 test counts (scratch venv and lock venv),
corpus size/load/memory, whole-app ~190 MB without SSR, OpenBLAS private-bytes artefact, Python 3.10/3.11 fail and 3.12/3.13 resolve,
HF doc facts (python_version default, preinstalls, CPU Basic, paid plan, Protected, env vars, sleep 48 h, ports), gradio analytics default,
httpx2 truststore, emulated downgrade with pydantic 2.13.5 and no-op with 2.12.5, lock closure on Linux, install sizes, mcp imported by `import gradio` in Space-like env.

Uncertain: the Sep 2026 builder still uses the Nov 2025 order and a python:3.12 base when python_version is "3.12" (no current public log);
Linux RSS equal to Windows WS (inferred only; no Linux run possible: Docker daemon stopped, only the docker-desktop WSL distro exists);
the foreign listener on 127.0.0.1:7861 (not present when I checked with netstat; transient).

Refuted or incomplete: "the whole app process ... about 190 MB (222 MB Space-like)" is incomplete for Spaces because SSR is on there by default and adds a Node process (~94 MB here).
Latency claim "p95 <= 0.43 ms" holds only for some query strings; I saw p95 up to 0.66 ms (still negligible).

## 5. New findings (not in the research)

1. SSR is on by default on Spaces (gradio env-var guide) and runs Node as the front proxy on the public port with Python behind it on an internal port
   (blocks.py; local log "Node proxy -> Python :63379"). Locally it adds ~94 MB and ~0.5 s to first 200; streaming of progress updates still works.
2. Visitor identity depends on SSR: behind the Node proxy the Python peer is 127.0.0.1, which uvicorn trusts by default, so `gr.Request.client.host`
   becomes the rightmost X-Forwarded-For entry (local test: XFF "203.0.113.7, 10.0.0.1" -> client.host "10.0.0.1"; single XFF -> that value).
   Without SSR, on Spaces the peer would be HF's proxy (not trusted), so client.host would be the proxy address (inferred, not tested on HF).
   The visitor-hash code (IP + browser info) must not rely on `request.client.host`; read X-Forwarded-For explicitly with a fixed rule and pin `ssr_mode` explicitly.
3. The Space build's last step installs **unpinned** `mcp` (gradio allows `>=1.21,<2`), `authlib`, `itsdangerous`, `spaces`, and their deps. mcp 1.x released 1.30.0 on 2026-09-07,
   so a new 1.x before 9/28 could bump shared deps (anyio, starlette, pydantic, httpx, uvicorn) silently. Pinning that closure in requirements.txt (21 extra pins, 76 total,
   no existing pin changes) makes step 4 a verified no-op (E12).
4. The sibling hf-spaces template (`plan3/hf-spaces/space_template/requirements.txt`) lists only 4 top-level pins and no pydantic hold; with it the Space would resolve pydantic 2.13.5 at step 3
   and downgrade to 2.12.5 at step 4. The gradio-ui and limits-store prototypes were run on pydantic 2.13.5. The consolidated Plan 3 must adopt the pydantic 2.12.5 hold.
5. HF Space Variables are publicly viewable; GRADIO_ANALYTICS_ENABLED=False is harmless there, but setting `os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")` at the top of app.py
   (before `import gradio`) needs no manual settings step and also covers local runs.
6. `gradio` default `concurrency_limit` is 1 per event listener: memory and CPU would allow many concurrent QA runs (they mostly wait on OpenAI), but Gradio would queue visitors one at a time
   unless Plan 3 sets `concurrency_limit` (UI-topic item; footprint is not the bottleneck).
7. `assistant.runner.run` constructs a new OpenAI client per call when `llm` is None; construction is cheap (ms) and clients are closed on GC, but the web layer can reuse one
   `OpenAIResponses` instance to keep one connection pool.
8. corpus/ is git-ignored and spec 13 says it is uploaded to the Space separately; the Protected Space keeps repo files private (spaces-overview), consistent with spec 1.2.

## 6. Decisions that should change

- Lock scope: keep the 55 app pins for local dev if wanted, but make the **Space requirements.txt the 76-pin file** (requirements-space-with-step4.txt: the 55 pins plus
  mcp 1.30.0, authlib 1.8.0, itsdangerous 2.2.0, spaces 0.51.3, requests 2.34.2, urllib3 2.7.0, charset-normalizer 3.5.1, attrs 26.1.0, cffi 2.1.1, cryptography 50.0.1,
  httpx-sse 0.4.3, joserfc 1.7.5, jsonschema 4.26.0, jsonschema-specifications 2025.9.1, pycparser 3.0, pydantic-settings 2.15.0, pyjwt 2.14.0, python-dotenv 1.2.3,
  referencing 0.37.0, rpds-py 2026.6.3, sse-starlette 3.4.11), and run local tests on the same set, so the last build step cannot change anything.
  Still re-run the emulation on deploy day.
- Footprint estimate: plan with ~0.3 GB (Python ~0.2 GB + Node SSR ~0.1 GB), and choose `ssr_mode` explicitly in `launch()` rather than inheriting the Spaces default, because it changes both memory and how the visitor address reaches Python.
- Analytics: set GRADIO_ANALYTICS_ENABLED in app.py before importing gradio (a Space Variable is optional, not required).
