"""Run the fake QA once without Gradio and save its record as the example-gallery replay (with event gaps)."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from assistant.runner import run
from slow_fake import fake_corpus, qa_script

stamps = []
t0 = time.monotonic()
result = run("qa", {"question": "2023년 한미 정상회담은 어디서 열렸어?", "years": [2023]},
             lambda kind, **d: stamps.append(round(time.monotonic() - t0, 3)), llm=qa_script(0.6), corpus=fake_corpus())
record = result.record
prev = 0.0
for event, t in zip(record["events"], stamps):
    event["t"] = t
    event["t_gap"] = round(t - prev, 3)
    prev = t
(ROOT / "measurements").mkdir(exist_ok=True)
(ROOT / "measurements" / "example_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
print(result.status, result.notice, result.usage["cost_krw"], [e["event"] for e in record["events"]])
print([s["badge"] for s in result.answer["sentences"]])
print(json.dumps(result.answer["references"], ensure_ascii=False)[:400])
