"""Automatic grading of QA run records against gold items (spec 8.3) and the report (spec 8.4)."""
from __future__ import annotations

from collections import Counter

from assistant.citations import VERIFIED, cite_key
from evals.gold import FACT_KINDS


def grade(item: dict, record: dict) -> dict:
    reasons: list[str] = []
    status = record["status"]
    if status != item["expect_status"]:
        reasons.append(f"상태 {status} (기대 {item['expect_status']})")
    answer = record.get("answer") or {"sentences": [], "references": []}
    if item["kind"] in FACT_KINDS:
        text = cite_key(" ".join(s["text"] for s in answer["sentences"]))
        missing = [group[0] for group in item["facts"] if not any(cite_key(alt) in text for alt in group)]
        if missing:
            reasons.append("답에 없는 사실: " + ", ".join(missing))
        verified_pages = {ref["page_id"] for ref in answer["references"] if ref["grade"] == VERIFIED}
        if not verified_pages & set(item["gold_pages"]):
            reasons.append("정답 쪽을 확인된 근거로 인용하지 않음")
    invented = sum(1 for s in answer["sentences"] for c in s["citations"] if c["reason"] == "page_not_read")
    if invented:
        reasons.append(f"읽지 않은 쪽을 인용 {invented}개")
    usage = record["usage"]
    return {"id": item["id"], "kind": item["kind"], "passed": not reasons, "reasons": reasons, "status": status,
            "elapsed_s": record["elapsed_s"], "cost_krw": usage["cost_krw"], "tokens": usage["tokens"],
            "grades": dict(Counter(s["grade"] for s in answer["sentences"]))}


def summarize(rows: list[dict]) -> dict:
    by_kind: dict[str, dict] = {}
    for row in rows:
        entry = by_kind.setdefault(row["kind"], {"passed": 0, "total": 0})
        entry["total"] += 1
        entry["passed"] += int(row["passed"])
    return {"passed": sum(int(row["passed"]) for row in rows), "total": len(rows), "by_kind": by_kind,
            "cost_krw": sum(row["cost_krw"] for row in rows),
            "elapsed_s": round(sum(row["elapsed_s"] for row in rows), 1)}


def render_report(summary: dict, rows: list[dict], title: str) -> str:
    lines = [f"# {title}", "", f"- 합격 {summary['passed']} / {summary['total']}",
             f"- 요금 약 {summary['cost_krw']:,}원, 걸린 시간 {summary['elapsed_s']}초", "",
             "| 종류 | 합격 | 전체 |", "|---|---|---|"]
    lines += [f"| {kind} | {v['passed']} | {v['total']} |" for kind, v in summary["by_kind"].items()]
    lines += ["", "| 문항 | 종류 | 합격 | 상태 | 시간(초) | 요금(원) | 입력 토큰 | 출력 토큰 | 이유 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['id']} | {row['kind']} | {'O' if row['passed'] else 'X'} | {row['status']} | "
                     f"{row['elapsed_s']} | {row['cost_krw']} | {row['tokens']['input']:,} | "
                     f"{row['tokens']['output']:,} | {'; '.join(row['reasons'])} |")
    return "\n".join(lines) + "\n"
