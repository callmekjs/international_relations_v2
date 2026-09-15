"""Re-check of the researcher's usage_ledger_sketch.py with cases its own smoke test masked."""
import json, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from usage_ledger_sketch import UsageLedger, visitor_key, kst_day

out = {}
with tempfile.TemporaryDirectory() as tmp:
    salt = b"s"
    v = visitor_key("203.0.113.7", "UA", salt)
    led = UsageLedger(Path(tmp), budget_krw=10_000)
    with ThreadPoolExecutor(16) as pool:
        grants = list(pool.map(lambda _: led.try_reserve(v, "qa")[0], range(50)))
    for ok in grants:
        if ok:
            led.record(v, "qa", 30.0)
    out["granted_of_50_parallel"] = sum(grants)
    re = UsageLedger(Path(tmp), budget_krw=10_000)  # restart, budget NOT reached
    out["after_restart_same_visitor_qa"] = re.try_reserve(v, "qa")
    out["after_restart_same_visitor_table"] = re.try_reserve(v, "table")
    # presenter spend counts toward the visitors' daily budget in the sketch?
    re.record("presenter", "qa", 9_950.0, presenter=True)
    out["new_visitor_after_presenter_spent_9950"] = re.try_reserve(visitor_key("198.51.100.2", "UA", salt), "qa")
    # in-flight overshoot: budget 100, 10 visitors reserve before any record
    led2 = UsageLedger(Path(tmp) / "b", budget_krw=100)
    granted = [led2.try_reserve(visitor_key(f"10.0.0.{i}", "UA", salt), "qa")[0] for i in range(10)]
    for i, ok in enumerate(granted):
        if ok:
            led2.record(visitor_key(f"10.0.0.{i}", "UA", salt), "qa", 90.0)
    out["inflight_granted_with_budget_100"] = sum(granted)
    out["inflight_total_krw"] = led2.totals.krw
    # same IP, different UA -> new visitor (cap evasion by changing browser info)
    out["same_ip_new_ua_allowed"] = re.try_reserve(visitor_key("203.0.113.7", "UA2", salt), "qa")
print(json.dumps(out))
