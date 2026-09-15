"""Per-question and per-summary cost model for gpt-5.6-sol / terra / luna (OpenAI Responses API).

    python cost_model.py            # prints tables, writes cost_results.json
    python cost_model.py --json     # JSON only

Token sizes come from measurements.json (tiktoken o200k_base, cross-checked with POST /v1/responses/input_tokens).
Reasoning tokens CANNOT be measured without generation calls: they are parameters (see SCENARIOS, sensitivity).
Standard library only.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).parent
KRW_PER_USD = 1400
BUDGET_KRW = 20_000
DAILY_CAP_KRW = 4_000  # spec 6.3 layer 3
LONG_CONTEXT_THRESHOLD = 272_000  # ">272K input tokens" -> long-context rates for the full request

# USD per 1M tokens, Standard processing (developers.openai.com/api/docs/pricing, read 2026-09-15)
PRICES = {
    "gpt-5.6-sol":   {"short": dict(input=4.00, cached=0.40, write=5.00, output=20.00),
                      "long":  dict(input=8.00, cached=0.80, write=10.00, output=30.00)},
    "gpt-5.6-terra": {"short": dict(input=2.00, cached=0.20, write=2.50, output=12.00),
                      "long":  dict(input=4.00, cached=0.40, write=5.00, output=18.00)},
    "gpt-5.6-luna":  {"short": dict(input=0.20, cached=0.02, write=0.25, output=1.20),
                      "long":  dict(input=0.40, cached=0.04, write=0.50, output=1.80)},
}
MIN_CACHEABLE = 1024  # "1,024 visible input tokens" for GPT-5.6 and later

# ---------------------------------------------------------------------------------------------- measured sizes
M = json.loads((HERE / "measurements.json").read_text(encoding="utf-8"))["derived"]
TOOLS_TOKENS = M["tools_tokens"]                        # 419 (4 strict function tools, prompt_assets.py)
DEV_OVERHEAD = M["developer_message_overhead"]          # 4
QUESTION_MSG = M["question_message_tokens"]             # 23 for a 27-char question (incl. request base)
ROUND_OVERHEAD = round(M["round_overhead_mean"])        # 23 per function_call + function_call_output pair
ARGS = M["function_call_args_tokens"]                   # search 18, read5 35, read4 29, get_toc 6
OUT_FORMAT = 10       # ASSUMPTION: non-visible formatting tokens per generated item (docs: exist, not itemized)
STATUS_CALL = 25      # ASSUMPTION: report_status(status, note) call incl. formatting


@dataclass
class Step:
    tool: str
    args: int
    result: int  # tokens of the tool output JSON


def search(stat="mean"):
    return Step("search", ARGS["search"], round(M["search_k10_tokens"][stat]))


def read5(stat="mean"):
    return Step("read_pages(5)", ARGS["read5"], round(M["read_pages5_tokens"][stat]))


def read4(stat="mean"):
    return Step("read_pages(4)", ARGS["read4"], round(M["read_pages4_tokens"][stat]))


def toc(stat="mean"):
    return Step("get_toc", ARGS["get_toc"], round(M["get_toc_tokens"][stat]))


@dataclass
class Scenario:
    name: str
    steps: list[Step]
    reasoning_tool: int      # reasoning tokens in each request that ends in a tool call
    reasoning_final: int     # reasoning tokens in the request that writes the answer
    answer: int              # visible answer tokens
    system_text: int = 1200  # developer prompt text tokens (task assumption; our draft measured 1,184)
    question_extra: int = 0  # extra question tokens beyond the measured 17-token example
    reasoning_carry: float = 1.0  # share of earlier reasoning tokens re-rendered as input (GPT-5.6 default all_turns)
    notes: str = ""

    @property
    def static_prefix(self) -> int:  # tools + developer message (identical for every visitor)
        return TOOLS_TOKENS + self.system_text + DEV_OVERHEAD


@dataclass
class Req:
    input: int
    output: int
    reasoning: int
    cached: int = 0
    write: int = 0
    uncached: int = 0
    usd: float = 0.0


def build_requests(s: Scenario) -> list[Req]:
    reqs = []
    inp = s.static_prefix + QUESTION_MSG + s.question_extra
    prev_reasoning = 0
    for i, step in enumerate(s.steps + [None]):
        if i > 0:
            last = s.steps[i - 1]
            inp += round(s.reasoning_carry * prev_reasoning) + last.args + ROUND_OVERHEAD + last.result
        if step is None:  # final answer (+ report_status in the same response)
            reqs.append(Req(inp, s.reasoning_final + s.answer + OUT_FORMAT + STATUS_CALL, s.reasoning_final))
        else:
            reqs.append(Req(inp, s.reasoning_tool + step.args + OUT_FORMAT, s.reasoning_tool))
            prev_reasoning = s.reasoning_tool
    return reqs


def apply_cache(reqs: list[Req], mode: str, static_prefix: int) -> list[Req]:
    """mode:
    none          prompt_cache_options.mode='explicit' with no breakpoints -> no reads, no writes
    implicit_cold default implicit mode; nothing cached before the question (idle > 30 min)
    implicit_warm implicit + explicit breakpoint after the developer message, and that prefix is still cached
                  from an earlier question (< 30 min ago)
    Implicit rule used: each request writes everything after its longest cached prefix up to its last
    eligible message (user message / last tool output), and the next request reads that whole prefix."""
    out, written = [], 0  # written = length of prefix known to be cached
    for i, r in enumerate(reqs):
        r = replace(r)
        if mode == "none":
            r.uncached = r.input
        else:
            if i == 0:
                written = static_prefix if (mode == "implicit_warm" and static_prefix >= MIN_CACHEABLE) else 0
            r.cached = written
            new_prefix = r.input  # breakpoint at end of the latest eligible message = end of input here
            if new_prefix >= MIN_CACHEABLE:
                r.write = new_prefix - r.cached
                written = new_prefix
            r.uncached = r.input - r.cached - r.write
        out.append(r)
    return out


def price(reqs: list[Req], model: str) -> float:
    total = 0.0
    for r in reqs:
        p = PRICES[model]["long" if r.input > LONG_CONTEXT_THRESHOLD else "short"]
        r.usd = (r.uncached * p["input"] + r.cached * p["cached"] + r.write * p["write"]
                 + r.output * p["output"]) / 1e6
        total += r.usd
    return total


SCENARIOS = {
    "low": Scenario("low", [search(), read4(), read4()], reasoning_tool=150, reasoning_final=500, answer=500,
                    notes="search + 2x read_pages(4 pages, mean size); reasoning.effort low-ish; short answer"),
    "typical": Scenario("typical", [search(), read5(), read4()], reasoning_tool=500, reasoning_final=1500,
                        answer=700, notes="search + read_pages(5) + read_pages(4), mean sizes; the 4-request loop "
                                          "whose visible input was measured with the counting endpoint"),
    "high": Scenario("high", [toc("max"), search("max"), search("max"), read5("p90"), read5("p90")],
                     reasoning_tool=1500, reasoning_final=4000, answer=900, question_extra=150,
                     notes="get_toc + 2 searches + 2x read_pages(5, p90 size); heavy reasoning; long question"),
}
MODES = ["none", "implicit_cold", "implicit_warm"]


def question_cost(s: Scenario, model: str, mode: str) -> dict:
    reqs = apply_cache(build_requests(s), mode, s.static_prefix)
    usd = price(reqs, model)
    return {"usd": usd, "krw": usd * KRW_PER_USD, "per_20k_krw": BUDGET_KRW / (usd * KRW_PER_USD),
            "requests": len(reqs), "sum_input": sum(r.input for r in reqs), "sum_cached": sum(r.cached for r in reqs),
            "sum_write": sum(r.write for r in reqs), "sum_output": sum(r.output for r in reqs),
            "sum_reasoning": sum(r.reasoning for r in reqs),
            "input_usd": sum((r.uncached * PRICES[model]["short"]["input"] + r.cached * PRICES[model]["short"]["cached"]
                              + r.write * PRICES[model]["short"]["write"]) / 1e6 for r in reqs),
            "trace": [r.__dict__ for r in reqs]}


def summary_cost(input_tokens: int, summary_out: int, reasoning: int, model: str, mode: str) -> dict:
    r = Req(input_tokens, summary_out + reasoning + OUT_FORMAT, reasoning)
    [r] = apply_cache([r], "none" if mode == "none" else "implicit_cold", 0)
    usd = price([r], model)
    return {"usd": usd, "krw": usd * KRW_PER_USD, "input": r.input, "write": r.write, "output": r.output}


def worst_case_qa(model: str, mode: str, tool_calls: int = 10, cap_input: int = 200_000) -> dict:
    """Spec 4.4 limit check: up to 10 tool calls of read_pages(5, max size), heavy reasoning, cumulative input cap."""
    s = Scenario("worst", [read5("max")] * tool_calls, reasoning_tool=1500, reasoning_final=4000, answer=900,
                 question_extra=150)
    reqs = build_requests(s)
    cum, kept = 0, []
    final_output = s.reasoning_final + s.answer + OUT_FORMAT + STATUS_CALL
    for r in reqs:
        if r is not reqs[-1] and cum + r.input > cap_input:
            # the app would not start another tool round: it forces the answer on this input instead
            kept.append(Req(r.input, final_output, s.reasoning_final))
            cum += r.input
            break
        kept.append(r)
        cum += r.input
    reqs = apply_cache(kept, mode, s.static_prefix)
    usd = price(reqs, model)
    return {"requests": len(reqs), "cumulative_input": cum, "last_input": reqs[-1].input,
            "usd": usd, "krw": usd * KRW_PER_USD}


def calibration_check() -> dict:
    """Rebuild the 4-request loop measured with the counting endpoint (reasoning 0, draft prompt 1,184 tokens,
    actual payloads 1,926 / 3,226 / 2,634) and compare visible input sizes."""
    s = Scenario("calib", [Step("search", ARGS["search"], 1926), Step("read5", ARGS["read5"], 3226),
                           Step("read4", ARGS["read4"], 2634)], reasoning_tool=0, reasoning_final=0, answer=0,
                 system_text=M["developer_message_text_tokens_draft"])
    model_inputs = [r.input for r in build_requests(s)]
    measured = M["loop_requests_measured"]
    return {"model": model_inputs, "measured": measured,
            "max_abs_diff": max(abs(a - b) for a, b in zip(model_inputs, measured))}


def status_roundtrip_extra(model: str) -> dict:
    """If report_status is sent back as a function_call_output, one more request follows the answer."""
    s = SCENARIOS["typical"]
    reqs = build_requests(s)
    last = reqs[-1]
    extra_in = last.input + round(s.reasoning_carry * s.reasoning_final) + s.answer + STATUS_CALL + ROUND_OVERHEAD
    reqs.append(Req(extra_in, 20 + OUT_FORMAT, 0))
    with_extra = price(apply_cache(reqs, "implicit_cold", s.static_prefix), model)
    base = price(apply_cache(build_requests(s), "implicit_cold", s.static_prefix), model)
    return {"extra_krw": (with_extra - base) * KRW_PER_USD, "total_krw": with_extra * KRW_PER_USD}


def run() -> dict:
    res = {"prices": PRICES, "krw_per_usd": KRW_PER_USD, "scenarios": {}, "sensitivity": {}, "summary": {},
           "calibration": calibration_check(),
           "status_roundtrip_typical": {m: status_roundtrip_extra(m) for m in PRICES}}
    for key, s in SCENARIOS.items():
        res["scenarios"][key] = {"notes": s.notes, "steps": [st.__dict__ for st in s.steps],
                                 "reasoning_tool": s.reasoning_tool, "reasoning_final": s.reasoning_final,
                                 "answer": s.answer, "models": {}}
        for model in PRICES:
            res["scenarios"][key]["models"][model] = {mode: question_cost(s, model, mode) for mode in MODES}
    # sensitivity: typical loop, sol, vary reasoning per request and carry
    base = SCENARIOS["typical"]
    for model in PRICES:
        rows = []
        for rt, rf in [(0, 0), (250, 500), (500, 1500), (1000, 3000), (2000, 6000), (4000, 12000)]:
            for carry in (1.0, 0.0):
                s = replace(base, reasoning_tool=rt, reasoning_final=rf, reasoning_carry=carry)
                q = question_cost(s, model, "implicit_cold")
                n = question_cost(s, model, "none")
                rows.append({"reasoning_tool": rt, "reasoning_final": rf, "carry": carry,
                             "krw_implicit_cold": q["krw"], "krw_no_cache": n["krw"], "per_20k": q["per_20k_krw"]})
        res["sensitivity"][model] = rows
    # summaries
    chapters = M["largest_chapter_api_tokens"]
    biggest_year = max(chapters, key=lambda y: chapters[y]["api_total_with_prompt"])
    big = chapters[biggest_year]["api_total_with_prompt"]
    summ = {"largest_chapter": {"year": biggest_year, **chapters[biggest_year]}, "cases": {}}
    cases = {"low": (1500, 1000), "typical": (3000, 3000), "high": (5000, 10000)}
    for model in PRICES:
        summ["cases"][model] = {c: {m: summary_cost(big, o, rsn, model, m) for m in ("none", "implicit")}
                                for c, (o, rsn) in cases.items()}
    prompt_overhead = big - 70741  # measured: summary prompt + message overhead (173)
    ch25 = M["chapters_2025"]
    summ["all_2025_chapters_typical"] = {
        model: sum(summary_cost(c["payload_tokens"] + prompt_overhead, 3000, 3000, model, "none")["krw"]
                   for c in ch25) for model in PRICES}
    summ["all_2025_input_tokens"] = sum(c["payload_tokens"] + prompt_overhead for c in ch25)
    res["summary"] = summ
    res["worst_case_qa_cap"] = {model: {m: worst_case_qa(model, m) for m in ("none", "implicit_cold")}
                                for model in PRICES}
    return res


def fmt_table(res: dict) -> str:
    c = res["calibration"]
    L = [f"Calibration vs counting endpoint (visible input, no reasoning): model {c['model']} measured "
         f"{c['measured']} max diff {c['max_abs_diff']} tokens"]
    L.append("Extra request if report_status output is sent back (typical, implicit_cold): " + ", ".join(
        f"{m} +{v['extra_krw']:.0f} KRW" for m, v in res["status_roundtrip_typical"].items()))
    for key in SCENARIOS:
        sc = res["scenarios"][key]
        L.append(f"\n## QA scenario: {key} -- {sc['notes']}")
        L.append(f"   reasoning/request={sc['reasoning_tool']}, final reasoning={sc['reasoning_final']}, answer={sc['answer']}")
        L.append(f"{'model':14} {'cache mode':14} {'reqs':>4} {'in(sum)':>8} {'cached':>7} {'write':>7} {'out(sum)':>8} "
                 f"{'USD':>8} {'KRW':>7} {'Q/20k KRW':>9}")
        for model, modes in sc["models"].items():
            for mode, q in modes.items():
                L.append(f"{model:14} {mode:14} {q['requests']:>4} {q['sum_input']:>8,} {q['sum_cached']:>7,} "
                         f"{q['sum_write']:>7,} {q['sum_output']:>8,} {q['usd']:>8.4f} {q['krw']:>7.0f} "
                         f"{q['per_20k_krw']:>9.0f}")
    L.append("\n## Request trace: typical, gpt-5.6-sol, implicit_cold")
    for i, r in enumerate(res["scenarios"]["typical"]["models"]["gpt-5.6-sol"]["implicit_cold"]["trace"], 1):
        L.append(f"  req{i}: input={r['input']:,} cached={r['cached']:,} write={r['write']:,} "
                 f"out={r['output']:,} (reasoning {r['reasoning']:,}) usd={r['usd']:.4f}")
    L.append("\n## Sensitivity (typical loop, implicit_cold): KRW per question by reasoning tokens")
    L.append(f"{'model':14} {'r/tool':>6} {'r/final':>7} {'carry':>5} {'KRW cached':>10} {'KRW no-cache':>12} {'Q/20k':>6}")
    for model, rows in res["sensitivity"].items():
        for r in rows:
            L.append(f"{model:14} {r['reasoning_tool']:>6} {r['reasoning_final']:>7} {r['carry']:>5} "
                     f"{r['krw_implicit_cold']:>10.0f} {r['krw_no_cache']:>12.0f} {r['per_20k']:>6.0f}")
    s = res["summary"]
    lc = s["largest_chapter"]
    L.append(f"\n## Summary of the largest chapter once: {lc['year']} {lc['chapter']} "
             f"({lc['pages']} pages, {lc['chars']:,} chars, {lc['api_total_with_prompt']:,} input tokens)")
    L.append("   cases: low=1,500 out + 1,000 reasoning; typical=3,000 + 3,000; high=5,000 + 10,000")
    for model, cases in s["cases"].items():
        parts = [f"{c}: {v['none']['krw']:.0f} KRW (implicit write {v['implicit']['krw']:.0f})" for c, v in cases.items()]
        L.append(f"  {model:14} " + " | ".join(parts))
    L.append(f"  All 7 main chapters of 2025 ({s['all_2025_input_tokens']:,} input tokens, typical output each, "
             f"no cache): " + ", ".join(f"{m} {v:.0f} KRW" for m, v in s["all_2025_chapters_typical"].items()))
    L.append("\n## Spec 4.4 cap check (10 x read_pages(5, max size), heavy reasoning, 200K cumulative input cap)")
    for model, modes in res["worst_case_qa_cap"].items():
        L.append(f"  {model:14} " + " | ".join(
            f"{m}: {v['requests']} reqs, cum input {v['cumulative_input']:,}, {v['krw']:.0f} KRW" for m, v in modes.items()))
    return "\n".join(L)


if __name__ == "__main__":
    results = run()
    (HERE / "cost_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        print(f"KRW/USD={KRW_PER_USD}; budget {BUDGET_KRW:,} KRW = ${BUDGET_KRW / KRW_PER_USD:.2f}")
        print(fmt_table(results))
