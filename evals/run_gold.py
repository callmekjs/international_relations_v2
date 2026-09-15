"""Run the gold questions through the real assistant. Costs money: typically about 250원 per question.

    PYTHONUTF8=1 .venv/Scripts/python.exe -m evals.run_gold --confirm

Without --confirm it only says how many questions would run. Records and report.md go to
evals/runs/<time>/ (git-ignored)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from assistant.runner import ROOT, hash_identifier, run
from evals.gold import load_gold
from evals.grade import grade, render_report, summarize

RUNS_DIR = ROOT / "evals" / "runs"


def run_gold(items: list[dict], *, llm, corpus, out_dir: Path, ask=run) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in items:
        result = ask("qa", {"question": item["question"], "years": item["years"]}, llm=llm, corpus=corpus,
                     safety_identifier=hash_identifier("gold-eval"))
        (out_dir / f"{item['id']}.json").write_text(json.dumps(result.record, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
        rows.append(grade(item, result.record))
        print(f"{item['id']} {'O' if rows[-1]['passed'] else 'X'} {result.status} 약 {rows[-1]['cost_krw']}원", flush=True)
    summary = summarize(rows)
    (out_dir / "report.md").write_text(render_report(summary, rows, f"정답지 시험 {out_dir.name}"), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="정답지 시험 (실제 요금 발생)")
    parser.add_argument("--confirm", action="store_true", help="요금이 드는 실제 실행에 동의")
    args = parser.parse_args(argv)
    items = load_gold()
    if not args.confirm:
        print(f"{len(items)}문항을 실제로 돌립니다. 보통 문항당 약 250원입니다. 돌리려면 --confirm 을 붙이세요.")
        return 2
    from assistant.llm_openai import OpenAIResponses
    from assistant.runner import default_corpus

    out_dir = RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    summary = run_gold(items, llm=OpenAIResponses(), corpus=default_corpus(), out_dir=out_dir)
    print(f"합격 {summary['passed']} / {summary['total']}, 약 {summary['cost_krw']:,}원, 성적표 {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
