"""Ask one question from the terminal. Real OpenAI calls, so it costs money.

    PYTHONUTF8=1 .venv/Scripts/python.exe -m assistant.ask "2023년 한미 정상회담은 어디서 열렸어?" --years 2023
    PYTHONUTF8=1 .venv/Scripts/python.exe -m assistant.ask --table runs/20260916-101500-qa.json

Shows the work as it happens, the answer with evidence badges, token use and cost, and saves the run
record to runs/ (git-ignored). --table prints the per-turn usage of a saved record."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from assistant.citations import CORRECTION_LABELS
from assistant.pricing import krw
from assistant.runner import ROOT, Result, run

RUNS_DIR = ROOT / "runs"
DONE, WARN, SKIP, WAIT, RETRY = "\u2713", "\u26a0", "\u2717", "\u2026", "\u21bb"


def format_event(kind: str, data: dict) -> str | None:
    if kind == "thinking":
        return f"  {WAIT} 생각 중"
    if kind == "tool_finished":
        return f"  {DONE if data['ok'] else WARN} {data['summary']}"
    if kind == "tool_skipped":
        return f"  {SKIP} 도구 한도에 닿아 건너뜀 ({data['name']})"
    if kind == "answer_started":
        return f"  {WAIT} 답 정리 중"
    if kind == "retrying":
        return f"  {RETRY} 다시 시도 {data['attempt']}번째 ({data['delay_s']}초 뒤)"
    return None  # a notice is shown once, by render_result


def render_result(result: Result) -> str:
    lines = ["", f"상태: {result.status}"]
    if result.answer:
        lines.append("")
        for sentence in result.answer["sentences"]:
            refs = "".join(f"[{n}]" for n in sentence["refs"])
            lines.append(" ".join(part for part in (sentence["text"], refs, f"({sentence['badge']})") if part))
        if result.answer["references"]:
            lines += ["", "근거"]
        for ref in result.answer["references"]:
            fixed = f", {CORRECTION_LABELS[ref['corrected']]}" if ref["corrected"] else ""
            lines.append(f"[{ref['n']}] {ref['label']} {ref['paragraph']}문단 '{ref['quote']}' ({ref['badge']}{fixed})")
    if result.notice:
        lines.append(f"안내: {result.notice['message']}")
    usage, tokens = result.usage, result.usage["tokens"]
    lines += ["", f"요청 {usage['turns']}번, 도구 {usage['tool_calls']}번, 입력 {tokens['input']:,}토큰"
                  f"(캐시 {tokens['cached']:,}), 출력 {tokens['output']:,}토큰(추론 {tokens['reasoning']:,}), "
                  f"약 {usage['cost_krw']:,}원, 걸린 시간 {result.record.get('elapsed_s')}초"]
    return "\n".join(lines)


def turn_table(record: dict) -> str:
    rows = ["| 요청 | 도구 선택 | 받은 항목 | 입력 | 캐시 읽기 | 캐시 쓰기 | 출력 | 추론 | 요금(원) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for turn in record["turns"]:
        u = turn["usage"]
        rows.append(f"| {turn['n']} | {turn['tool_choice']} | {', '.join(turn['items'])} | {u['input']:,} | "
                    f"{u['cached']:,} | {u['cache_write']:,} | {u['output']:,} | {u['reasoning']:,} | "
                    f"{krw(turn['cost_usd'])} |")
    return "\n".join(rows)


def save_record(record: dict, out_dir: Path = RUNS_DIR) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path, n = out_dir / f"{stamp}-{record['task']}.json", 1
    while path.exists():
        path, n = out_dir / f"{stamp}-{n}-{record['task']}.json", n + 1
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def main(argv: list[str] | None = None, *, llm=None, corpus=None, out_dir: Path = RUNS_DIR) -> int:
    parser = argparse.ArgumentParser(description="외교백서 AI 조수에게 질문 하나 하기 (실제 요금 발생)")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--years", default="", help="쉼표로 구분한 연도. 예: 2023,2024")
    parser.add_argument("--table", help="저장된 실행 기록의 요청별 사용량 표를 출력")
    args = parser.parse_args(argv)
    if args.table:
        if not Path(args.table).is_file():
            parser.error(f"기록 파일이 없습니다: {args.table}")
        print(turn_table(json.loads(Path(args.table).read_text(encoding="utf-8"))))
        return 0
    if not args.question:
        parser.error("질문을 쓰거나 --table 을 주세요")
    parts = [part.strip() for part in args.years.split(",") if part.strip()]
    if not all(part.isascii() and part.isdigit() for part in parts):
        parser.error(f"--years 에는 2023,2024처럼 연도 숫자를 쉼표로 구분해 적어 주세요: {args.years}")
    years = [int(part) for part in parts] or None

    def on_event(kind: str, **data) -> None:
        line = format_event(kind, data)
        if line:
            print(line, flush=True)

    result = run("qa", {"question": args.question, "years": years}, on_event, llm=llm, corpus=corpus)
    print(render_result(result))
    print(f"기록: {save_record(result.record, out_dir)}")
    return 1 if result.status == "error" else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
