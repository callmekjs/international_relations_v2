# 외교백서 AI 조수

외교부 외교백서(2020~2025년치 6권)를 LLM(OpenAI gpt-5.6-sol)이 직접 찾아 읽고, 근거 쪽수와 함께 답하는 앱이다.
설계서: `docs/superpowers/specs/2026-09-14-whitepaper-ai-assistant-design.md`

## 준비 (Windows, Git Bash)

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-prep.txt
```

- `requirements.txt`: 앱 실행에 필요한 것 (Hugging Face Space에 설치)
- `requirements-prep.txt`: 백서 준비와 시험까지 (PyMuPDF, pytest 추가)

## 백서 준비 (한 번)

`data/`에 백서 PDF를 두고 실행한다.

```bash
PYTHONUTF8=1 .venv/Scripts/python.exe -m prep.build
```

`corpus/`가 생긴다. `data/`와 `corpus/`는 저작권 때문에 git에 올리지 않는다.

## 시험

```bash
PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest
```

- 시험은 OpenAI API를 부르지 않는다 (요금 0원).
- `-m "not slow"`를 붙이면 6권 코퍼스를 통째로 만드는 시험을 뺀다.
- PDF나 PyMuPDF가 없는 곳(예: `requirements.txt`에 pytest만 더 설치한 곳)에서는 PDF 시험이 저절로 건너뛰어진다. `requirements.txt`에는 pytest가 없으니 시험을 돌리려면 pytest를 따로 설치한다.

## OpenAI 열쇠

프로젝트 폴더의 `.env`에 한 줄로 넣는다. `.env`는 git에 올리지 않는다.

```
OPENAI_API_KEY=sk-...
```

공개 앱의 열쇠는 `.env`가 아니라 Hugging Face Space의 Secrets에 넣는다.

## 질문 하나 해 보기 (실제 요금 발생)

```bash
PYTHONUTF8=1 .venv/Scripts/python.exe -m assistant.ask "2023년 한미 정상회담은 어디서 열렸어?" --years 2023
```

일하는 과정, 근거 대조 결과(확인됨 / 문단만 확인 / 근거 없음), 토큰과 요금이 나오고, 실행 기록이 `runs/`에 저장된다.
보통 질문 1번에 약 190~250원, 한도 안에서 최대 약 1,500원이다.
`--table runs/파일.json`으로 요청별 토큰 표를 볼 수 있다.

## 정답지 시험 (실제 요금 발생)

```bash
PYTHONUTF8=1 .venv/Scripts/python.exe -m evals.run_gold --confirm
```

`evals/gold.jsonl`의 18문항을 돌려 자동으로 채점하고, 기록과 성적표(`report.md`)를 `evals/runs/<시각>/`에 저장한다.
보통 문항당 약 250원이다. `--confirm` 없이 실행하면 돌리지 않고 안내만 한다.
