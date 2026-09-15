"""Summary cost table from chapters.json, priced with the repository's assistant/pricing.py (read-only import).

Reasoning volume is the open variable. Scenarios (reasoning tokens as a function of visible output V):
- low:      0.5 x V
- measured: 1.78 x V   (first live check, final-answer turn: 286 reasoning / 161 visible, effort low)
- high:     5,000 + 3 x V
- ceiling:  output = max_output_tokens (32,000), the most one request can bill
Input uses prompt_cache_options.mode = "explicit" with no breakpoints: no cache writes, no reads.
Batch has the same per-token prices as Flex on the pricing page, so batch = flex here.

    PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe summary_costs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "C:/international_relations")
from assistant.llm import Usage  # noqa: E402
from assistant.pricing import USD_TO_KRW, cost_usd  # noqa: E402

HERE = Path(__file__).resolve().parent
MODEL = "gpt-5.6-sol"
MAX_OUTPUT = 32_000
BUDGET_KRW = 20_000
LIVE_RATIO = 286 / 161


def reasoning(v: int, scenario: str) -> int:
    return {"low": round(0.5 * v), "measured": round(LIVE_RATIO * v), "high": 5_000 + 3 * v}[scenario]


def cost(input_tokens: int, output_tokens: int, tier: str, implicit_cache: bool = False) -> float:
    usage = Usage(input=input_tokens, cache_write=input_tokens if implicit_cache else 0, output=output_tokens)
    return cost_usd(usage, MODEL, "flex" if tier in ("flex", "batch") else "default")


def krw(usd: float) -> int:
    return round(usd * USD_TO_KRW)


def main() -> None:
    data = json.loads((HERE / "chapters.json").read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r["kind"] == "chapter"]
    s = data["summary"]
    pick = lambda y, l: next(r for r in rows if r["year"] == y and r["label"] == l)  # noqa: E731
    groups = {
        "(a) all 7 chapters of 2025": [r for r in rows if r["year"] == 2025],
        "(b) largest: 2023 제3장 (108 pp)": [pick(2023, "제3장")],
        "(c) typical (median): 2023 제2장 (31 pp)": [pick(s["median_chapter"]["year"], s["median_chapter"]["label"])],
        "(d) smallest: 2022 제7장 (7 pp)": [pick(2022, "제7장")],
        "(e) all 44 main chapters, 2020-2025": rows,
    }
    table = {}
    for name, members in groups.items():
        inp = sum(r["input_tokens_est"] for r in members)
        vis = sum(r["visible_output_est"] for r in members)
        entry = {"requests": len(members), "input_tokens": inp, "visible_output_tokens": vis, "scenarios": {}}
        for scenario in ("low", "measured", "high"):
            outs = [r["visible_output_est"] + reasoning(r["visible_output_est"], scenario) for r in members]
            entry["scenarios"][scenario] = {
                "output_tokens": sum(outs),
                **{tier: krw(sum(cost(r["input_tokens_est"], o, tier) for r, o in zip(members, outs)))
                   for tier in ("standard", "flex", "batch")}}
        entry["scenarios"]["ceiling_32k_output"] = {
            "output_tokens": MAX_OUTPUT * len(members),
            **{tier: krw(sum(cost(r["input_tokens_est"], MAX_OUTPUT, tier) for r in members))
               for tier in ("standard", "flex", "batch")}}
        entry["implicit_cache_default_extra_krw_standard"] = krw(
            sum(cost(r["input_tokens_est"], 0, "standard", True) - cost(r["input_tokens_est"], 0, "standard")
                for r in members))
        table[name] = entry

    typical = table["(c) typical (median): 2023 제2장 (31 pp)"]["scenarios"]
    per_budget = {sc: {tier: (BUDGET_KRW // max(1, typical[sc][tier])) for tier in ("standard", "flex")}
                  for sc in ("low", "measured", "high")}
    # per-chapter cost at the measured ratio, for the report table
    per_chapter = [{"year": r["year"], "label": r["label"], "input": r["input_tokens_est"],
                    "output_measured": r["visible_output_est"] + reasoning(r["visible_output_est"], "measured"),
                    "standard_krw": krw(cost(r["input_tokens_est"], r["visible_output_est"]
                                             + reasoning(r["visible_output_est"], "measured"), "standard")),
                    "flex_krw": krw(cost(r["input_tokens_est"], r["visible_output_est"]
                                         + reasoning(r["visible_output_est"], "measured"), "flex"))}
                   for r in rows]
    result = {"model": MODEL, "usd_to_krw": USD_TO_KRW, "live_ratio_reasoning_per_visible": round(LIVE_RATIO, 2),
              "groups": table, "summaries_per_20000_krw_typical_chapter": per_budget, "per_chapter_measured": per_chapter}
    (HERE / "summary_costs_output.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_chapter_measured"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
