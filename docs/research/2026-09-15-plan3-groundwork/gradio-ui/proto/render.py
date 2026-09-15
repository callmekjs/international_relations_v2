"""Server-side rendering of progress lines and answers. Every string that came from the model, the visitor
or the corpus goes through esc(); only these templates write markup."""
from __future__ import annotations

import html

DONE, WARN, SKIP, WAIT, RETRY = "✓", "⚠", "✗", "…", "↻"
MOFA_BOARD_URL = "https://www.mofa.go.kr/www/brd/m_4105/list.do"  # placeholder, not checked (groundwork note)
BADGE_CLASS = {"verified": "b-ok", "paragraph_only": "b-para", "unsupported": "b-none"}
CORRECTION_LABELS = {"paragraph": "문단 바로잡음", "page": "쪽 바로잡음"}

CSS = """
.run-steps{margin:0;padding-left:1.2em;font-size:.95em;line-height:1.6}
.run-steps li.pending{opacity:.75}
.ai-label{display:inline-block;font-size:.75em;padding:0 .4em;border:1px solid currentColor;border-radius:4px;margin-left:.4em}
.badge{display:inline-block;font-size:.8em;padding:0 .45em;border-radius:4px;margin-left:.3em;white-space:nowrap}
.b-ok{background:#d9f2e3;color:#135c2f}.b-para{background:#fff1c2;color:#6b4e00}.b-none{background:#e6e6e6;color:#444}
.refs{padding-left:0;list-style:none}.refs li{margin:.35em 0;overflow-wrap:anywhere}
.quote{color:#555}
@media (max-width:640px){.run-steps{font-size:.9em}.badge{font-size:.75em}}
"""


def esc(text) -> str:
    """HTML-escape, then neutralise ` and $ as well, so the text stays inert even if it ever ends up inside
    a gr.HTML template literal (the HTML component evaluates its template as a JS template string)."""
    return html.escape(str(text), quote=True).replace("`", "&#96;").replace("$", "&#36;")


def step_line(kind: str, data: dict) -> tuple[str, str] | None:
    """(state, text) for one progress event; None for events that are not shown as a line."""
    if kind == "thinking":
        return "pending", f"{WAIT} 생각 중"
    if kind == "tool_requested":
        return "pending", f"{WAIT} 도구 요청: {data.get('name')}"
    if kind == "tool_finished":
        return "done", f"{DONE if data.get('ok') else WARN} {data.get('summary')}"
    if kind == "tool_skipped":
        return "done", f"{SKIP} 도구 한도에 닿아 건너뜀 ({data.get('name')})"
    if kind == "answer_started":
        return "pending", f"{WAIT} 답 정리 중"
    if kind == "retrying":
        return "pending", f"{RETRY} 다시 시도 {data.get('attempt')}번째 ({data.get('delay_s')}초 뒤)"
    return None


def apply_line(lines: list[tuple[str, str]], line: tuple[str, str] | None) -> bool:
    """Keep at most one pending line at the end: a new line replaces a trailing pending one."""
    if line is None:
        return False
    if lines and lines[-1][0] == "pending":
        lines[-1] = line
    else:
        lines.append(line)
    return True


def progress_html(lines: list[tuple[str, str]], *, running: bool, elapsed_s: float | None = None) -> str:
    title = "조수가 일하는 과정"
    tail = f" ({elapsed_s:.0f}초)" if elapsed_s is not None else ""
    items = "".join(f'<li class="{state}">{esc(text)}</li>' for state, text in lines)
    status = " · 진행 중" if running else ""
    return (f'<details open><summary>{esc(title)}{esc(status)}{esc(tail)}</summary>'
            f'<ol class="run-steps">{items}</ol></details>')


def answer_html(result) -> str:
    """Answer sentences with [n] references, badges, 'AI 생성' label, reference list and the MOFA link."""
    parts: list[str] = []
    if result.answer:
        sentences = []
        for s in result.answer["sentences"]:
            refs = "".join(f"<sup>[{int(n)}]</sup>" for n in s["refs"])
            badge = f'<span class="badge {BADGE_CLASS.get(s["grade"], "b-none")}">{esc(s["badge"])}</span>'
            sentences.append(f"<p>{esc(s['text'])}{refs}{badge}</p>")
        parts.append(f'<h4>답<span class="ai-label">AI 생성</span></h4>{"".join(sentences)}')
        refs = []
        for r in result.answer["references"]:
            fixed = f' <span class="badge b-para">{esc(CORRECTION_LABELS[r["corrected"]])}</span>' if r["corrected"] else ""
            refs.append(f'<li>[{int(r["n"])}] {esc(r["label"])} {int(r["paragraph"])}문단 '
                        f'<span class="quote">“{esc(r["quote"])}”</span>'
                        f'<span class="badge {BADGE_CLASS.get(r["grade"], "b-none")}">{esc(r["badge"])}</span>{fixed}</li>')
        if refs:
            parts.append(f'<h4>근거</h4><ul class="refs">{"".join(refs)}</ul>')
        parts.append(f'<p><a href="{esc(MOFA_BOARD_URL)}" target="_blank" rel="noopener noreferrer">'
                     f'→ 외교부 원문 받으러 가기</a></p>')
    if result.notice:
        parts.append(f'<p class="notice">안내: {esc(result.notice["message"])}</p>')
    return "".join(parts) or f"<p>{esc('상태: ' + str(result.status))}</p>"


def chat_progress(lines: list[tuple[str, str]], *, running: bool, duration_s: float | None):
    """Variant B: the same lines as one 'thought' message in gr.Chatbot (metadata title/status/duration)."""
    import gradio as gr

    body = "\n".join(f"- {esc(text)}" for _, text in lines) or "-"
    meta = {"title": "조수가 일하는 과정", "status": "pending" if running else "done"}
    if duration_s is not None and not running:
        meta["duration"] = round(duration_s, 1)
    return gr.ChatMessage(role="assistant", content=body, metadata=meta)
