"""Prototype of the white-paper assistant screen (spec 6.2). Fake model, made-up corpus, no network.

    PYTHONUTF8=1 ../venv/Scripts/python.exe app.py            # http://127.0.0.1:7861 only

Env: PRESENTER_PASSWORD (default "demo-pass" for the prototype), PROTO_TURN_S (fake turn length),
PROTO_PORT, VISITOR_IP_SOURCE (client | xff_first | xff_last)."""
from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import gradio as gr  # noqa: E402

from assistant.runner import run  # noqa: E402
from bridge import EventLog, RunHandle, stream_run  # noqa: E402
from render import CSS, answer_html, apply_line, chat_progress, esc, progress_html, step_line  # noqa: E402
from slow_fake import fake_corpus, qa_script  # noqa: E402

KST = timezone(timedelta(hours=9))
MEASURE = ROOT / "measurements"
MEASURE.mkdir(exist_ok=True)
LOG = EventLog(MEASURE / "server_events.jsonl")
TURN_S = float(os.environ.get("PROTO_TURN_S", "1.2"))
SALT = os.environ.get("VISITOR_SALT") or secrets.token_hex(16)   # a Space secret in the real app
PRESENTER_PASSWORD = os.environ.get("PRESENTER_PASSWORD", "demo-pass")
DAILY_CAPS = {"qa": 3}
MAX_UNLOCK_FAILS = 5
API_VIS = os.environ.get("PROTO_API", "private")  # "public" only for the gradio_client timing checks

_lock = threading.Lock()
USAGE: dict[tuple[str, str, str], int] = {}      # (day, visitor, task) -> count; the Storage Bucket in Plan 3
UNLOCK_FAILS: dict[tuple[str, str], int] = {}
ACTIVE: dict[str, RunHandle] = {}                # session_hash -> running handle
RESULTS: list[dict] = []                          # finished runs (for the headless checks)


# --- visitor --------------------------------------------------------------------------------------
def visitor_info(request: gr.Request) -> dict:
    headers = {k.lower(): v for k, v in dict(request.headers).items()}
    chain = [p.strip() for p in headers.get("x-forwarded-for", "").split(",") if p.strip()]
    client_host = request.client.host if request.client else ""
    source = os.environ.get("VISITOR_IP_SOURCE", "client")
    ip = {"xff_first": chain[0] if chain else client_host,
          "xff_last": chain[-1] if chain else client_host}.get(source, client_host)
    browser = "|".join(headers.get(h, "") for h in ("user-agent", "accept-language"))
    key = hashlib.sha256(f"{SALT}|{ip}|{browser}".encode("utf-8")).hexdigest()
    return {"key": key, "session_hash": request.session_hash, "client_host": client_host, "xff_chain": chain,
            "ip_source": source}


def today() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def reserve(visitor: str, task: str, unlocked: bool) -> tuple[bool, int]:
    """Count the use before the run starts (a closed tab must not make the question free)."""
    if unlocked:
        return True, -1
    with _lock:
        key = (today(), visitor, task)
        used = USAGE.get(key, 0)
        if used >= DAILY_CAPS[task]:
            return False, 0
        USAGE[key] = used + 1
        return True, DAILY_CAPS[task] - used - 1


def check_password(given: str) -> bool:
    """Constant-time compare of fixed-length digests, so neither content nor length leaks through timing."""
    if not PRESENTER_PASSWORD:
        return False
    a = hashlib.sha256(given.encode("utf-8")).digest()
    b = hashlib.sha256(PRESENTER_PASSWORD.encode("utf-8")).digest()
    return hmac.compare_digest(a, b)


# --- handlers -------------------------------------------------------------------------------------
def unlock(password: str, unlocked: bool, request: gr.Request):
    v = visitor_info(request)
    fail_key = (today(), v["key"])
    if UNLOCK_FAILS.get(fail_key, 0) >= MAX_UNLOCK_FAILS:
        return unlocked, "시도 횟수를 넘었어요. 내일 다시 해 주세요.", ""
    if check_password(password or ""):
        LOG.write(where="handler", what="unlock_ok", session_hash=request.session_hash)
        return True, "발표 모드: 방문자·하루 한도를 건너뜁니다.", ""
    UNLOCK_FAILS[fail_key] = UNLOCK_FAILS.get(fail_key, 0) + 1
    return unlocked, "비밀번호가 맞지 않아요.", ""


def account(result, handle: RunHandle) -> None:
    """Runs in the worker thread when run() returns, even after the visitor left."""
    RESULTS.append({"run": handle.id, "status": result.status, "notice": result.notice,
                    "cost_krw": result.usage["cost_krw"], "turns": result.usage["turns"],
                    "cancel_reason": handle.cancel_reason})
    (MEASURE / f"record-{handle.id}.json").write_text(json.dumps(result.record, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")


def ask(question: str, years: list[str], unlocked: bool, request: gr.Request):
    v = visitor_info(request)
    LOG.write(where="handler", what="request", session_hash=v["session_hash"], client_host=v["client_host"],
              xff_chain=v["xff_chain"], visitor_key=v["key"][:12],
              headers=sorted(k.lower() for k in dict(request.headers)))
    if not (question or "").strip():   # validate before counting, so an empty click costs no quota
        yield "", "<p>질문을 입력해 주세요.</p>", [], gr.skip()
        return
    allowed, left = reserve(v["key"], "qa", unlocked)
    if not allowed:
        yield ("", "<p>오늘 질문 한도를 다 썼어요. '예시 모음'은 계속 볼 수 있어요.</p>",
               [], "오늘 남은 질문 0번")
        return
    remaining = "발표 모드" if left < 0 else f"오늘 남은 질문 {left}번"
    handle = RunHandle()
    ACTIVE[request.session_hash] = handle
    lines: list[tuple[str, str]] = []
    started = time.monotonic()
    inputs = {"question": question, "years": [int(y) for y in years] or None}
    yield progress_html(lines, running=True), "", [chat_progress(lines, running=True, duration_s=None)], remaining
    try:
        for item in stream_run(lambda on_event: run("qa", inputs, on_event, llm=qa_script(TURN_S),
                                                    corpus=fake_corpus()),
                               handle, on_result=account, log=LOG, heartbeat_s=1.0, deadline_s=240):
            if item[0] == "event":
                if not apply_line(lines, step_line(item[1], item[2])):
                    continue
                LOG.write(run=handle.id, where="generator", what="yield", kind=item[1])
                yield (progress_html(lines, running=True), gr.skip(),
                       [chat_progress(lines, running=True, duration_s=None)], gr.skip())
            elif item[0] == "tick":
                yield (progress_html(lines, running=True, elapsed_s=item[1]), gr.skip(), gr.skip(), gr.skip())
            elif item[0] == "result":
                result = item[1]
                elapsed = time.monotonic() - started
                LOG.write(run=handle.id, where="generator", what="yield", kind="result")
                done_lines = [(st, t) for st, t in lines if st != "pending"]  # drop the trailing "... 답 정리 중"
                yield (progress_html(done_lines, running=False, elapsed_s=elapsed), answer_html(result),
                       [chat_progress(done_lines, running=False, duration_s=elapsed)], remaining)
            else:
                yield gr.skip(), f"<p>{esc('문제가 생겼어요: ' + type(item[1]).__name__)}</p>", gr.skip(), gr.skip()
    finally:
        ACTIVE.pop(request.session_hash, None)


def stop(request: gr.Request):
    handle = ACTIVE.get(request.session_hash)
    LOG.write(where="handler", what="stop_clicked", session_hash=request.session_hash, found=handle is not None)
    if handle:
        handle.stop("stop_button")


def on_unload(request: gr.Request):
    handle = ACTIVE.get(request.session_hash)
    LOG.write(where="handler", what="unload", session_hash=request.session_hash, found=handle is not None)
    if handle:
        handle.stop("unload")


def replay(name: str):
    """Example gallery: replays a saved record's events (0 KRW). Records keep no event times yet, so pace them."""
    path = MEASURE / "example_record.json"
    if not path.is_file():
        yield "<p>예시 기록이 아직 없어요.</p>", ""
        return
    record = json.loads(path.read_text(encoding="utf-8"))
    lines: list[tuple[str, str]] = []
    for event in record["events"]:
        kind = event["event"]
        data = {k: v for k, v in event.items() if k != "event"}
        if not apply_line(lines, step_line(kind, data)):
            continue
        yield progress_html(lines, running=True), ""
        time.sleep(event.get("t_gap", 0.5))

    class Saved:  # the shape answer_html() reads
        status, answer, notice = record["status"], record["answer"], record["notice"]

    yield progress_html([("done", t) for _, t in lines], running=False), answer_html(Saved)


def make_csv():
    rows = [["항목", "내용", "근거"], ["정상회담", "워싱턴", "2023년치 38쪽"]]
    out = ROOT / "_downloads"
    out.mkdir(exist_ok=True)
    path = out / f"table-{datetime.now(KST):%Y%m%d-%H%M%S}.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:   # BOM: Excel opens Korean text correctly
        csv.writer(f).writerows(rows)
    return gr.DownloadButton(value=str(path), visible=True)


# --- layout ---------------------------------------------------------------------------------------
THEME = gr.themes.Default(font=["system-ui", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", "sans-serif"])

with gr.Blocks(title="외교백서 AI 조수 (시제품)") as demo:
    unlocked = gr.State(False)
    gr.Markdown("## 외교백서 AI 조수 · 시제품")
    with gr.Tabs():
        with gr.Tab("질문답변", id="qa"):
            question = gr.Textbox(label="질문", max_length=300, lines=2,
                                  placeholder="2023년 한미 정상회담은 어디서 열렸어?")
            years = gr.CheckboxGroup(["2020", "2021", "2022", "2023", "2024", "2025"], label="연도 (선택)")
            with gr.Row():
                ask_btn = gr.Button("물어보기", variant="primary")
                stop_btn = gr.Button("멈추기", variant="stop")
            remaining = gr.Markdown("오늘 남은 질문 3번")
            progress = gr.HTML(elem_id="progress")
            answer = gr.HTML(elem_id="answer")
            with gr.Accordion("비교용: Chatbot thought 표시", open=False):
                chat = gr.Chatbot(label="진행", height=260, buttons=["copy"], feedback_options=None,
                                  elem_id="chat")
        with gr.Tab("요약", id="summary"):
            gr.Markdown("연도와 장을 고르면 저장된 요약을 보여 줍니다 (계획 3).")
        with gr.Tab("표 뽑기", id="table"):
            csv_btn = gr.Button("예시 CSV 만들기")
            download = gr.DownloadButton("CSV 받기", visible=False, elem_id="csv")
        with gr.Tab("비교", id="compare"):
            gr.Markdown("비교는 나중에 만듭니다.")
        with gr.Tab("예시 모음", id="examples"):
            example = gr.Dropdown(["2023 한미 정상회담"], value="2023 한미 정상회담", label="예시")
            replay_btn = gr.Button("다시 보기")
            replay_progress = gr.HTML()
            replay_answer = gr.HTML()
    with gr.Accordion("발표용", open=False):
        password = gr.Textbox(label="발표용 비밀번호", type="password")
        unlock_msg = gr.Markdown()

    ask_event = ask_btn.click(ask, [question, years, unlocked], [progress, answer, chat, remaining],
                              concurrency_limit=4, concurrency_id="llm", show_progress="hidden",
                              api_visibility=API_VIS)
    stop_btn.click(stop, None, None, cancels=[ask_event], queue=False, api_visibility=API_VIS)
    password.submit(unlock, [password, unlocked], [unlocked, unlock_msg, password], api_visibility=API_VIS)
    csv_btn.click(make_csv, None, download, api_visibility=API_VIS)
    replay_btn.click(replay, example, [replay_progress, replay_answer], concurrency_limit=None,
                     api_visibility=API_VIS)
    demo.unload(on_unload)

demo.queue(default_concurrency_limit=1, max_size=20)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=int(os.environ.get("PROTO_PORT", "7861")), theme=THEME, css=CSS,
                footer_links=[], enable_monitoring=False, run_history=False, show_error=False, ssr_mode=False)
