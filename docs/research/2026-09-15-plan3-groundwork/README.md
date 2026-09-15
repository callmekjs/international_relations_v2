# 계획 3 사전 조사 기록 — 화면 · 인터넷 공개 · 요약 · 한도 (2026-09-15)

> **2026-09-15 주석님 결정**: 문제 신고 연락처 GitHub Issues, 질문 기록 30일 보관, 달 단위 방문자 멈춤 12,600원 넣기(P22 확정), 탭 순서 [질문답변] [예시 모음] [요약] [표 뽑기] [비교](P14 확정), 이용 안내 초안(digest 부록 A) 승인, 설계서 고칠 곳 S1~S22 승인.

계획 3(화면 + Hugging Face 공개 + 요약 + 방문자 한도 + 예시 모음)을 쓰기 전에 조사 5개를 돌리고, 조사마다 반박 검증을 붙였다.
**OpenAI 호출 0번 · Hugging Face 계정 작업 0번 · 요금 0원.** 저장소는 읽기만 했다(git status 깨끗).
검증이 조사를 뒤집은 곳은 검증 쪽을 따랐다. 자세한 근거(출처 URL, 실험 숫자)는 영어로 쓴 `digest.md`에 있다.

> 이 폴더의 코드는 조사 · 검증용 시제품이다. 앱에서 import 하지 않는다. 구현은 계획 3에서 시험과 함께 새로 만든다.
> 저장소(`docs/research/2026-09-15-plan3-groundwork/`)로 옮기면서 `venv` · `wheels` · 문서 사본(`pages/`, `refs/`) · Gradio 소스 사본은 뺐다(용량 · 저작권). 옮긴 파일과 뺀 것은 7장에 있다.

---

## 1. 조사 목록과 검증 결과

| 조사 | 반박 검증 (맞음 / 틀림 / 불확실) | 핵심 |
|---|---|---|
| 화면 (gradio-ui) | 35 / 0 / 2 | 조수를 따로 일꾼(스레드)에서 돌리면 진행 줄이 실시간(브라우저에 그려지기까지 8.5~18.4ms)으로 온다. **창을 닫아도 돈이 계속 나가서** 멈춤 장치가 필요하다. `gr.HTML`은 아무것도 걸러 주지 않는다 → 모든 글자를 이스케이프. 대기 줄 크기는 모든 기능의 합계라 작게 두면 예시 모음까지 막힌다 |
| 인터넷 공개 (hf-spaces) | 26 / 1 / 1 | PRO + CPU Basic + Protected + Storage Bucket(`/data`)으로 된다. README에 `python_version: "3.12"`를 꼭 적어야 한다. 저장소 폴더를 통째로 올리면 `.gitignore` 때문에 **corpus가 조용히 빠진다.** Space는 기본으로 SSR(앞에 Node 프로그램)이 켜져 PC 시험과 달라진다 → 끈다 |
| 설치 (deps) | 23 / 1 / 2 | Gradio 6.27.0과 openai 3.14.0은 함께 설치 · 실행된다(시험 174개 통과). Space 빌드가 마지막에 pydantic을 2.12.5로 **몰래 내린다** → 76줄 설치 목록으로 막는다. 앱 메모리 약 0.2GB(SSR 켜면 0.3GB), CPU Basic 16GB의 2% 미만 |
| 요약 (summary) | 30 / 2 / 4 | 요약할 본문 장은 44개, 가장 큰 장(2023년치 제3장)은 입력 약 6.7만 토큰. gpt-5.6-sol은 **Flex를 지원**한다(정확히 절반 값). 보통 장 약 270원(Flex 140원), 2025년치 7장 전부 Flex 약 970원. 요청 1번 출력 상한은 1.6만 → **3.2만**이 필요하다 |
| 한도 · 저장 · 안전 (limits-store-safety) | 31 / 2 / 5 | "시작할 때 예상 요금을 잡아 두고 끝나면 실제 요금으로 바꾸기"로 하루 4,000원 멈춤이 동시 요청에도 지켜진다. 검증에서 구멍 셋: 비밀번호 잠금 우회(200번 시도), 끊긴 요청의 요금 누락, 끝나지 않은 실행이 하루를 0원으로 닫음. 외교부 게시물 주소 6개 확인 |
| **합계** | **145 / 6 / 14** | |

**검증에서 틀린 것으로 판정된 6가지와 고친 방향**

| 조사가 말한 것 | 검증 결과 | 고친 결정 |
|---|---|---|
| 사용량 장부 시제품이 설계서 6.3대로 동작 | 발표용 요금이 방문자 하루 합계에 섞이고, 동시 실행 10개가 한도 100원에 900원까지 허용 | P18 · P21 |
| 앱 전체 메모리 약 190MB | Space는 SSR이 켜져 Node 프로그램 약 94MB가 더 붙음 | P12 (SSR 끔) |
| 요약 근거 대조는 최악 0.55초 | 없는 구절 1개당 0.03~0.06초. 54개면 약 3초, 형식 최대 297개면 14.6초 | P27 (대조 결과 저장) |
| 진행 줄 파서가 인용 속 `"title":`에 속을 수 있음 | JSON 안에서는 따옴표가 이스케이프돼 속지 않음 | 조치 없음 |
| 비밀번호 5번 틀리면 그날 잠금 | 브라우저 번호를 바꿔 한 IP에서 200번 시도 | P21 |
| 끊긴 요청도 요금이 잡힌다 | 조수 루프가 실패한 턴의 사용량을 버려 0원으로 보임 | P19 |

---

## 2. 계획 3에 반영하는 결정

### 2.1 설치 · 배포

| # | 결정 | 근거 |
|---|---|---|
| P1 | **76줄 설치 목록**을 저장소 `requirements.txt`와 Space에 똑같이 쓴다: `gradio==6.27.0`, `openai==3.14.0`, `bm25s==0.3.11`, `numpy==2.5.3`, `pydantic==2.12.5`, `pydantic-core==2.41.5`, `fsspec==2026.6.0` 등 55개 + Space 빌드 마지막 단계가 까는 `mcp==1.30.0` · `spaces==0.51.3` 등 21개(파일: `deps-verify/requirements-space-with-step4.txt`). `requirements-prep.txt`는 `-r requirements.txt` + `pymupdf==1.26.7` + `pytest`. 로컬 `.venv`도 이 목록으로 맞춘다 | 함께 설치 충돌 0건, `pip check` 통과. httpx 0.28.1(Gradio)과 httpx2 2.13.0(OpenAI)은 파일이 하나도 안 겹침. Space 빌드는 requirements.txt 뒤에 `gradio[oauth,mcp]`를 다시 까는데, mcp 옵션이 `pydantic<=2.12.5`를 요구해 2.13.5를 몰래 내림(흉내 빌드로 확인, pip는 성공으로 끝남). 76줄이면 마지막 단계가 아무것도 바꾸지 않음. pydantic 2.12.5에서 시험 174개 통과 |
| P2 | Space README: `sdk: gradio`, `sdk_version: 6.27.0`, `python_version: "3.12"`, `app_file: app.py`. `suggested_storage` · `preload_from_hub`는 쓰지 않는다. "README의 gradio 판 = 설치 목록 판" 시험을 둔다 | 기본 Python 3.10이면 numpy 2.5.3(3.12 이상)이 설치되지 않음(Linux 해석: 3.10 · 3.11 실패, 3.12 성공). 판이 다르면 빌드가 gradio를 바꿔 버림. 옛 영구 저장 상품은 없어졌고, preload는 비공개 저장소를 못 읽음 |
| P3 | 배포는 **허용 목록 묶음**만 올린다: `app.py`, `web/`, `assistant/`, `store/`, `corpus/`(10개), 예시 모음, 미리 만든 요약, `requirements.txt`, Space README. 묶음은 **저장소 밖**(임시 폴더)에 만들고, 열쇠 모양 글자가 있으면 거부(단어 경계 적용), 필수 파일을 확인한 뒤 `hf upload <이름>/<Space> <묶음> . --repo-type space`. 저장소 폴더를 통째로 올리거나 git push 하지 않는다. **올릴 때마다 주석님께 여쭌다** | 저장소에서 올리면 `.gitignore`가 서버에서 적용돼 `corpus/`가 빠짐. 기본 제외 목록에 `.env`가 없음. 실제 저장소 묶음 모의 실행: 27개 · 15,980,226바이트(재실행 같음). 저장소 안 `dist/`에 만들면 코드 사본이 git 제외가 안 돼 공개 GitHub에 올라갈 수 있음. `hf upload`는 지운 파일을 Space에서 지우지 않음(`--delete` 패턴 필요) |
| P4 | 백서 자료(corpus)는 Protected Space 안에 둔다. Space에 HF 토큰은 넣지 않는다. Gradio 파일 허용 경로(`allowed_paths`, `GRADIO_ALLOWED_PATHS`, `gr.set_static_paths`)에 앱 폴더 · corpus를 **절대 넣지 않고**, `/gradio_api/file=corpus/pages.jsonl`이 403인지 시험한다. Space를 Public으로 바꾸지 않는다 | Protected는 코드 · 파일 비공개, 앱 화면만 공개. 실험: corpus · app.py · 가짜 .env 모두 403(SSR 켬 · 끔 둘 다) |
| P5 | 비공개 Storage Bucket 1개를 `/data`에 읽기 · 쓰기로 연결하고, **실행 중에 생기는 것만** 쓴다(`usage/`, `runs/`, 방문자가 새로 만든 요약). 예시 모음과 미리 만든 요약은 배포 묶음에 넣는다. 요약은 Bucket → 묶음 순서로 찾는다 | Space 디스크는 재시작하면 지워짐. PRO 비공개 저장 1TB 포함이라 추가 요금 0. Bucket 연결이 고장 나도 0원 볼거리(설계서 6.3의 4겹)가 남아야 함 |
| P6 | Bucket에는 **새 파일을 한 번에 쓰고 닫기**만 한다(덧붙이기 · 덮어쓰기 · 이름 바꾸기 · 파일 잠금 · SQLite 금지). 쓰기는 따로 쓰기 스레드가 한다. 계수기는 메모리(잠금 1개)에 두고, 시작할 때 오늘 파일 + 지난날 합계 파일(`usage/_days/<날짜>.json`)을 백그라운드로 읽어 되살린다(끝날 때까지 "준비 중"). 저장소 점검(self-check)은 `launch()` 뒤 스레드에서 60초 제한으로 돌리고, 실패하면 메모리 한도만으로 계속 연다 | Space의 마운트 쓰기 방식은 문서에 없음. hf-mount 기본은 덧붙이기 전용 · 닫을 때 올림, NFS 방식은 2~30초 늦게 씀, 마지막에 쓴 것이 이김. 시제품: 동시 50번 예약 → 정확히 3개, 재시작 뒤 합계 복원, 깨진 파일은 건너뜀. 한 달치 4,350파일 되살리기 38~41초 → 날 합계가 있으면 0.27초. 점검이 멈추면 앱이 뜨지 않을 수 있음 |

### 2.2 화면

| # | 결정 | 근거 |
|---|---|---|
| P7 | `assistant.run`은 일꾼 스레드에서 돌리고, `on_event`가 큐에 넣은 줄을 Gradio 생성기가 하나씩 내보낸다. 생성기는 1초마다 빈 신호(tick)도 낸다. 진행 줄 · 답 · 근거는 서버에서 만든 HTML을 `gr.HTML`에 넣고, `show_progress="hidden"` | 실제 Chromium에서 줄이 생긴 뒤 그려지기까지 8.5~18.4ms, 14줄 모두 순서대로. tick이 없으면 Gradio가 생성기를 닫지 못함(`aclose`가 "실행 중"이면 기다림) |
| P8 | 멈춤 3가지 길: ① '멈추기' 버튼(`queue=False` 함수 + `cancels=[질문 이벤트]`) ② 창 닫힘(`demo.unload`) ③ 생성기 닫힘. 셋 다 멈춤 표시를 켜고, **새 인자 `assistant.run(..., should_stop=)`** 이 턴 시작 전 · 도구 실행 전 · 재시도 대기 전에 확인한다. 멈추면 상태 `cancelled` + 주인 경보 없는 안내. 턴 도중에는 끊지 않는다. 질문 1번 전체 마감 시간(예: 150초)도 같은 길로 멈춘다 | 그냥 두면 창을 닫은 뒤에도 남은 턴을 다 돌려 돈을 씀(5턴 전부, 15.3초에 끝남). 멈춤을 넣으니 창을 닫고 22~51ms 뒤 `unload`가 불리고 일꾼은 다음 이벤트에서 멈춤(81~285ms), 버튼은 약 0.9초. 지금 코드는 멈추면 `unknown` 안내(주인 경보)가 뜨고, 턴 도중에 끊으면 그 턴 사용량이 기록에서 빠짐. Gradio `time_limit`은 일반 생성기에 적용되지 않음 |
| P9 | **처음 만드는 요약은 방문자 연결과 떼어** 일꾼이 끝까지 만든다(같은 장은 잠금 1개). 창을 닫아도 저장되고, 보고 있는 사람은 진행 줄을 받는다. 질문답변은 P8대로 멈춘다 | 요약은 요청 1번이 수 분 걸릴 수 있고, 끊으면 이미 만든 토큰 값만 내고 저장이 안 됨(추론). 저장된 요약은 다음부터 0원 |
| P10 | 실행 기록 판 2: 이벤트마다 시작 뒤 초(`"t"`)를 적고, moderation에 걸린 분류 이름을 기록한다(`runner.py` 3곳, `tests/test_runner.py` 43 · 117줄). `session_hash`는 기록 · 화면 어디에도 남기지 않는다 | 지금 기록에는 이벤트 시각이 없어 예시 모음을 실제 속도로 재생할 수 없음. 시제품의 "재생 시간이 같다"는 elapsed_s를 나눠 만든 값이라 증명이 안 됨(검증). session_hash는 브라우저가 만든 값이라 남이 알면 그 창의 상태를 가져감 |
| P11 | 화면 안전: 모델 · 백서 · 방문자 글자는 모두 `esc()` = `html.escape` + 백틱과 `$`를 문자 참조로 바꾼 뒤 넣는다. `gr.HTML`은 **기본 템플릿(`${value}`)만** 쓰고 `{{ }}` 자리표시는 쓰지 않는다. 모델 글에 `gr.Markdown` · `gr.Chatbot`을 쓰지 않는다. 표는 `gr.Dataframe(datatype="str", interactive=False)`. 링크는 고정 외교부 주소만(`rel="noopener noreferrer"`). 공격 문자열 자동 시험을 둔다 | `gr.HTML`은 거르지 않음(onerror · svg script · ontoggle 실행). `{{value}}`에 넣은 `${...}`는 html.escape 뒤에도 JS로 실행되고, `$`를 바꾸면 멈춤. Markdown · Chatbot은 코드는 막지만 바깥 그림 주소를 불러옴(방문자 IP가 남에게 새어 나감). 이스케이프 + `gr.HTML`은 아무 반응 없음 |
| P12 | 서버 설정 묶음: `launch(ssr_mode=False, footer_links=[], enable_monitoring=False, run_history=False, show_error=False, mcp_server=False, pwa=False, max_file_size="1mb")`, `gr.Blocks(analytics_enabled=False, delete_cache=(3600, 3600))`, `app.py` 맨 위(gradio import 전)에 `os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")`, 모든 이벤트 `api_visibility="private"`. 한도 확인은 모두 서버 함수 안에서 한다 | Space에서는 SSR이 기본으로 켜져 PC 시험과 달라지고 메모리 +85~94MB, 방문자 IP 읽는 법도 바뀜. 기본 설정은 `/monitoring/summary` 공개, 업로드 크기 무제한(앱에 업로드 칸이 없어도 200KB 익명 업로드 성공, 서버 경로 노출). `private`은 문서에서만 숨김 — 직접 HTTP로 부르면 실행됨 |
| P13 | 대기 줄: `demo.queue(api_open=False, max_size=200, default_concurrency_limit=1)`. 요금이 드는 이벤트(질문 · 요약 · 표 · 비교)는 **모두 `concurrency_id="llm"`, `concurrency_limit=4`로 같은 숫자**. 0원 이벤트(예시 모음 · 저장된 요약 · 비밀번호)는 `concurrency_limit=None`으로 따로. 요금 드는 실행 + 대기가 12개(설정값)를 넘으면 앱이 "지금 붐벼요"라고 답하고 한도를 깎지 않는다. 요금 드는 일은 첫 `yield` 뒤에 시작한다 | Gradio 기본 동시 처리는 1(한 명씩). `max_size`는 **모든 이벤트의 합계**라 20이면 꽉 찰 때 예시 모음도 503. 같은 id에 숫자가 다르면 가장 작은 숫자가 처음 쓰일 때부터 재시작까지 적용됨(질문 4개 동시 → 1개씩으로 떨어짐). limit 4 시험: 6명 중 4명 즉시, 2명 대기. 로컬은 `api_open`이 열려 있어 대기 줄을 건너뛸 수 있음 |
| P14 | 한글 · 모양: 테마 글꼴 `system-ui, Apple SD Gothic Neo, Malgun Gothic, Noto Sans KR, sans-serif`(Google 글꼴을 받지 않음), 색은 테마 변수, 탭 순서는 **[질문답변] [예시 모음] [요약] [표 뽑기] [비교]** | 휴대폰 폭(375px)에서는 앞 탭 2개만 보이고 나머지는 "⋯" 안에 숨음 → 0원 볼거리를 앞으로. 다크 모드에서 고정 색은 잘 안 보임 |
| P15 | CSV 받기(표 뽑기 계획에서 씀): `gr.DownloadButton`, UTF-8 BOM, 모든 칸 따옴표, `= + - @` · 탭 · 줄바꿈 · 전각 기호로 시작하는 칸 앞에 `'`(보통 숫자 `-3.5%`는 그대로), 첫 줄에 "AI 생성 표" 표시 | BOM · 내려받기 헤더 확인. OWASP CSV 수식 주입 안내. 인공지능 기본법 해설: 서비스 밖으로 나가는 결과물에도 표시 |

### 2.3 한도 · 방문자

| # | 결정 | 근거 |
|---|---|---|
| P16 | 한국 날짜 = `timezone(timedelta(hours=9))`. 방문자 키 = `HMAC-SHA256(VISITOR_SALT, "v|날짜|IP|User-Agent 앞 300자|Accept-Language 앞 100자|browser_id")`, 앞 16자만 저장. IPv6는 /64까지만. `browser_id`는 `gr.BrowserState`의 임의 값(`storage_key` · `secret`은 코드 상수로 고정, 64자 제한, 믿지 않는 입력). 원래 IP · UA · 언어 값은 어디에도 남기지 않는다 | 결정된 "IP + 브라우저 정보 해시" 규칙 그대로에 브라우저 번호만 더함 → 같은 와이파이 · 같은 브라우저 청중이 한 사람으로 합쳐지지 않음. IPv4 해시는 43억 개를 다 넣어 보면 풀리므로 비밀 소금이 필요. BrowserState는 재시작마다 열쇠가 바뀌고 secret은 브라우저로 전달됨(비밀 아님) |
| P17 | 방문자 IP 규칙(임시): `X-Forwarded-For`의 **가장 오른쪽 공인 주소**, 없으면 `request.client.host`. 가장 왼쪽 값은 방문자가 꾸밀 수 있어 쓰지 않는다. 첫 배포 점검(4장 U1) 뒤 확정한다 | uvicorn은 127.0.0.1에서 온 요청만 XFF를 믿고 가장 오른쪽을 씀. SSR 켜기 · 끄기에 따라 `client.host`가 달라짐(실험). HF 프록시 동작은 문서에 없음. HF는 모든 요청에 `X-IP-Token`을 붙인다고 문서에 씀(점검 후보) |
| P18 | **예약 뒤 정산**: 입력 검사를 통과하면 시작 때 한도 칸을 깎고 예상 요금을 잡아 둔다(질문 150원, 새 요약은 장별 입력 토큰 + 출력 1.6만 토큰으로 계산해 약 480~820원, 표 · 비교 1,000원). "방문자 오늘 지출 + 잡아 둔 돈 + 이번 예상 ≤ 4,000원"일 때만 시작. 끝나면 실제 요금으로 바꾼다. 정산은 **일꾼 스레드의 `try/finally`** 에서 하고, 마감 시간보다 오래된 예약(질문 약 5분, 요약 약 20분)은 자동으로 푼다. 자정을 넘긴 실행은 시작한 날에 센다 | 동시 200명 시험: 25명 시작, 잡아 둔 돈 3,900원 ≤ 4,000원. 정산을 생성기 끝에 두면, 끝나지 않은 실행 27개가 0원 지출로 하루를 닫음(검증 실험). 자정을 넘긴 900원 실행이 오늘 합계에 0원으로 들어가던 구멍(검증) |
| P19 | **돌려주기 규칙**: 0원이면서 `busy`(429) · `budget` · `config_error` · `bad_request`로 끝난 실행만 칸을 돌려준다. `timeout` · `connection` · `server_error` · `stream_broken` · `unknown`은 칸을 쓰고 요금은 max(실제, 예상)으로 센다. moderation에 걸린 질문과 `cancelled`도 칸을 쓴다(요금은 실제). 저장된 요약 보기, 남이 만드는 중인 같은 장을 기다려 받은 요약은 0원 · 칸 안 씀 | 조수 루프는 실패한 턴의 사용량을 버림(`loop.py` LLMError 분기) → 끊긴 요청은 0원으로 보이지만 OpenAI는 청구했을 수 있음. 설계서 6.3의 요금 멈춤이 적게 세면 안 됨 |
| P20 | 같은 IP(날짜 키)는 하루 약 **1,000원**까지, 방문자당 동시 실행 1개, 시작 간격 10초. IP 한도 거절은 기록한다 | browser_id를 바꾸면 방문자 한도는 피할 수 있음(한 IP · 한 UA로 질문 30번, 검증). 표 · 비교 4~8번이면 4,000원 하루가 닫힘. 통신사 NAT는 여러 사람을 한 IP로 묶으므로 횟수보다 원 단위가 공평 |
| P21 | 발표용: 발표용 요금은 기록하되 **방문자 하루 합계에 넣지 않는다**. 비밀번호는 20자 이상 무작위, `type="password"` 칸, 서버에서 `hmac.compare_digest(sha256(입력), sha256(PRESENTER_PASSWORD))`, 입력 칸은 바로 비움. 시도는 IP 날짜 키마다 5초에 1번 · 하루 20번 틀림까지(전체 잠금 없음). 풀림은 그 창의 `gr.State`에만, 3시간 | 장부 시제품은 발표용 요금을 방문자 합계에 섞어 발표 날 방문자가 일찍 막힘(검증). "5번 틀리면 그날 잠금"은 브라우저 번호를 바꿔 200번 시도(검증). 전체 잠금은 청중 한 명이 발표자를 막을 수 있음. gr.State는 서버에 있어 브라우저가 보낸 값은 무시됨(실험) |
| P22 | **새 제안 — 달 단위 방문자 멈춤**: 한국 달 기준 방문자 합계가 12,600원(약 $9)을 넘으면 방문자 새 요청을 멈춘다. 발표용은 계속 쓴다. **주석님 확인 필요** | 발표용도 같은 공개용 OpenAI 프로젝트($12 강제 한도)를 씀. 강제 한도에 닿으면 발표자까지 다음 달 주기까지 막힘. 하루 4,000원이 여러 날 차면 발표 전에 한도를 넘을 수 있음. 반대로 이 멈춤이 9/28 전에 걸리면 청중은 예시 모음만 보게 됨 |
| P23 | `safety_identifier` = `HMAC(VISITOR_SALT, "s|IP|browser_id")`(날마다 바뀌지 않음, 64자). 발표용은 `HMAC(VISITOR_SALT, "presenter")`. OpenAI가 "identifier blocked"를 주면 그 IP 키 · browser_id를 그날 멈춘다. 발표용 창에서 공격성 질문 시험을 하지 않는다 | OpenAI는 식별값이 한결같기를 원하고, 막힌 식별값은 풀어 주지 못함. 로그인 없는 미리보기는 세션 id를 보내도 된다고 함. IP + UA만 쓰면 같은 기종 휴대폰끼리 겹쳐 남 때문에 영구 차단될 수 있음. 반복되면 조직 전체의 GPT-5 사용이 약 7일 뒤 멈출 수 있음 |

### 2.4 요약

| # | 결정 | 근거 |
|---|---|---|
| P24 | 요약 대상은 **본문 장 44개(제n장)만**. 부록과 장 밖 쪽은 요약하지 않는다. 미리 만들기는 2025년치 제1~7장 + 발표 시나리오의 장 | 부록은 표 · 일지 위주(해마다 51~78쪽)이고 2025년치 부록 조직도는 자료에 없음. 본문 장은 빠진 쪽 0, 절 개수가 44장 모두 목차와 일치(독립 재집계) |
| P25 | 요청 모양: 장 전체를 **절별 JSON(형식 B)** 으로 한 번에(`page_id` + 번호 붙은 문단). 도구 없음 — `turn()`은 도구 목록이 비면 `tools` · `tool_choice` 키를 **아예 뺀다**. `reasoning.effort` low, `store=False`, `stream=True`, `prompt_cache_options={"mode": "explicit"}`(중단점 없음 = 캐시 쓰기 요금 없음), moderation 없음(방문자 글이 없음), `max_output_tokens=32000`. 입력 상한은 장마다 미리 센 토큰 수로 확인한다 | 44장 합계 형식 B 932,840토큰. 지금 연결 파일은 `"tools": []`를 보냄(빈 목록 허용 여부는 문서에 없음, 빼면 확실). 캐시 쓰기를 안 하면 가장 큰 장 94원 · 2025년치 214원 절약. `limits.py`의 "글자당 1토큰"이면 2023년치 제3장(요청 113,178자, 실제 약 6.7만 토큰)이 10만 상한에 막힘. OpenAI는 추론 + 출력에 2.5만 토큰 이상 여유를 권장하고, 끊긴 strict JSON은 못 쓰는데 요금은 냄 |
| P26 | 답 형식 strict 스키마 `chapter_summary`: `sections`(절 제목 + 문장 1~8개) 먼저, `overview`(1~3문장) 나중, 문장마다 근거 1~3개(`page_id` · 문단 번호 · 구절). 절마다 문장 수는 프로그램이 정한다(1~3쪽 2, 4~9쪽 3, 10~19쪽 4, 20쪽 이상 5). 일감 설명서 `summary-2026-09-19`에 **"구절은 번호 붙은 문단 하나 안에서만 고른다"** 를 더한다. 설명서 · 스키마 · 입력 형식 · 문장 수 규칙 · effort가 바뀌었는데 판 번호를 안 올리면 실패하는 지문 시험. 결과의 절 개수 · 제목을 입력과 비교한다 | 두 문단에 걸친 구절은 50/50 "문단만 확인". 본문 장 "문단"의 약 55%가 30자 미만(제목 · 목록 줄). strict 출력은 스키마 키 순서를 따름. 스키마가 1~12절을 허용해 모델이 절을 합치거나 빼도 알 수 없음 |
| P27 | 근거 대조는 기존 `verify_answer`를 그대로 쓴다(절 문장 + 개요를 한 줄로 펴서 대조한 뒤 다시 절로 묶음, 읽은 쪽 = 그 장의 인용 가능한 모든 쪽). **대조 결과까지 저장**하고, 대조기 지문(`citations.py` + `textnorm.py` 해시)이나 자료 지문(`corpus_hash`)이 바뀔 때만 다시 대조한다 | 모든 판정 경로 확인(200/200 확인됨, 50/50 쪽 바로잡음). "최악 0.55초"는 틀림: 없는 구절 1개당 0.03~0.06초, 54개 2.8~3.4초, 스키마 최대 297개 14.6초 |
| P28 | 저장 키 `summaries/{year}/ch{NN}/{prompt_version}/{model}.json`(경로에 해시를 넣지 않음). 기록에 `corpus_hash` · `answer_raw` · 대조한 답 · 사용량 · `service_tier` · 이벤트(t). **완료되고 JSON이 해석된 것만** 저장한다. corpus_hash가 다르면 "오래됨 → 요청 때 새로 만듦" | 설계서 5.2의 키 + 자료를 다시 만들어 문단 번호가 바뀌는 경우 대비. 시제품 `storage_key()`는 해시를 경로에 넣어 "오래됨" 상태가 생기지 않음(검증) |
| P29 | Flex 미리 만들기: 로컬 명령(개발용 열쇠), `service_tier="flex"`, 요청 시간 900초. 결제 코드가 아닌 429와 503 `server_is_overloaded`는 max(Retry-After, 30 · 60 · 120 · 240초) 기다린 뒤 건너뛴다. `--fallback-standard`를 줄 때만 일반 요청으로 다시 보낸다. 결제 코드 · 400 `service_tier` 거부는 다시 시도하지 않는다. 확인됨 80% 미만인 장은 표시한다. Batch는 예비 | gpt-5.6-sol이 Flex 가격표에 있음(정확히 절반, Batch와 같음). Flex 자리 없음(429)은 청구 안 됨. 지금 재시도 규칙은 Retry-After가 20초를 넘으면 0번, 503은 0.5초 뒤 재시도 → Flex에 안 맞음(검증). Batch는 파일 올리기 · OpenAI에 30일 보관 · 진행 표시 없음 |
| P30 | 방문자 새 요약: 일반 요청, 요청 시간 600초. "글자가 화면에 나감"(재시도 멈춤) 기준은 **최종 답 메시지의 첫 글자**(`response.output_text.delta`)다. `queued` · `thinking` · `answer_started` 줄은 재시도를 막지 않는다 | 지금 연결 파일은 "생각 중" 줄만 떠도 나간 것으로 봐서, 긴 추론 중에 잠깐 끊겨도 재시도하지 않음(검증 실험). 설계서 4.3의 기준은 "글자" |
| P31 | 요약 진행 줄: `chapter_loaded`(쪽 · 절 · 토큰), `queued`, `section_started` · `sentences_written` · `overview_started`(최종 답 메시지의 글자 조각만 읽어 절 제목을 잡음), `checking` · `checked`(배지 개수), `saved`, `loaded_saved` + 경과 초 표시. `turn()`에 `on_text` 인자를 더한다 | 요약은 도구 단계가 없어 수 분 동안 보여줄 게 없음. 시제품이 1~9자 조각으로 끊어 넣어도 6개 절을 순서대로 잡음 |

### 2.5 예시 모음 · 안전 · 발표

| # | 결정 | 근거 |
|---|---|---|
| P32 | 예시 모음: Claude가 로컬에서 후보를 돌리고 **주석님이 한 건씩 보고 승인**한다. `web/gallery/index.json` + `items/<slug>.json`(0.9~2.5KB), 배포 묶음에 넣고 공개 GitHub에는 올리지 않는다(git 제외). 9/26까지 확정. 재생은 `asyncio.sleep` 생성기(1× · 2×, 간격 최대 6초), 실시간 화면과 같은 그리기 함수를 쓰고 `assistant.run` · OpenAI · corpus · 한도를 전혀 부르지 않는다. 발표 질문마다 같은 질문의 기록(쌍둥이)을 만든다 | OpenAI 공유 정책: 공유 전 사람이 검토, 이름 밝히기, AI 생성 표시. 항목에 백서 구절과 질문이 들어 있음. 네트워크를 막고 재생해도 동작(실험) |
| P33 | 외교부 링크(판별 고정): `https://www.mofa.go.kr/www/brd/m_4105/view.do?seq=` + 2020년치 **291** · 2021년치 **292** · 2022년치 **298** · 2023년치 **299** · 2024년치 **300** · 2025년치 **301**(내려받기 주소 `down.do`는 쓰지 않음). 구절은 화면 · 예시 모음에서 **80자까지** 보이고 넘으면 줄임표. 질문답변 설명서에도 긴 구절 복사 금지를 넣는다 | 6개 모두 HTTP 200, 제목 · 게시일 확인, 게시판 PDF 이름 = `corpus/volumes.json`. 공공누리 표시 없음 → 짧은 인용 + 출처(저작권법 제28 · 37조). 외교부 저작권 정책도 제24조의2(국가가 만든 저작물 이용)를 인용함. 지금 코드는 구절 길이를 제한하지 않음 |
| P34 | 이용 안내(화면에 늘 보이게, 초안은 `digest.md` 부록 A): AI가 만든 답 · 틀릴 수 있음, 모으는 것(질문 · 연도 · 답 · 사용량 · 되돌릴 수 없는 방문자 구분값), 질문 기록 30일 보관, OpenAI(미국) 전송, 개인정보를 쓰지 말 것, **만 19세 미만** 보호자 동의, '문제 신고' 연락처, 외교부와 무관. 기록: 방문자 실행 기록(질문 포함) 30일(한국 0시 넘어갈 때마다 삭제), 사용량 줄은 2026-12-31까지. 서버 로그에는 실행 id · 기능 · 상태 · 요금 · 시간만 | 인공지능 기본법 제31조(2026-01-22 시행, 개인도 사업자에 들 수 있음): 미리 알리기 · 결과 표시. OpenAI 약관 §3.3(c) 미성년자 보호자 동의(한국 성년은 19세), §16.12 지원 국가. OpenAI 남용 감시 기록 30일. "시작할 때 삭제"는 재시작 없이 30일이 지나면 안 돌아감 |
| P35 | 발표 운영: 마지막 배포 9/26, **9/27부터 동결**(코드 올리기 · 비밀값 · 변수 · Bucket 연결 · `hf spaces hot-reload` 모두 금지). 9/27과 발표 30분 전에 주석님이 **로그인한 상태로** Space 상태 확인(Paused면 설정에서 재시작) + 발표용 비밀번호로 짧은 질문 1개. 발표 중 45초 동안 새 진행 줄이 없거나 오류가 나면 "미리 돌려 둔 같은 질문 기록" 버튼. 노트북 로컬 대체(개발용 열쇠로 실시간, 또는 예시 모음만), 휴대폰 핫스팟, 설정 · 대시보드 화면은 띄우지 않음 | 코드를 올리거나 비밀값을 바꾸면 재시작(풀림 · 실행 중인 작업이 사라짐). CPU Basic은 48시간 방문이 없으면 잠듦. 문서 한 곳은 "Paused"(주인만 재시작)라고 씀. GPT-5.6은 스트림 중 몇 초 멈출 수 있음 |

---

## 3. 설계서 고칠 곳 (주석님 승인 뒤 반영, 설계서는 아직 고치지 않음)

대상: `docs/superpowers/specs/2026-09-14-whitepaper-ai-assistant-design.md`

**S1 · 3.1 부품 표 `store/` 행** (P5 · P6)
- 지금: "저장된 요약, 실행 기록(예시 모음 · 성적표용), 사용량 | Hugging Face Storage Bucket"
- 바꿈: "방문자가 새로 만든 요약, 실행 기록, 사용량 · 요금 정산 | Hugging Face Storage Bucket(`/data`, 새 파일 쓰기만). 미리 만든 요약과 예시 모음은 배포 묶음에 넣어 읽기 전용으로 둔다(Bucket이 고장 나도 남게)"

**S2 · 3.1 부품 사이 약속, `assistant.run` 항목** (P8 · P10)
- 더함: "  - `should_stop`(선택)을 받는다. 매 턴 시작 · 도구 실행 · 재시도 대기 전에 확인하고, 멈추면 상태 `cancelled`로 끝낸다. 턴 도중에는 끊지 않는다."
- 더함: "  - 실행 기록의 이벤트마다 시작 뒤 초(`t`)를 적는다(예시 모음 재생용)."

**S3 · 3.2 흐름** (P18)
- 지금: "→ web: 한도 확인 (방문자 · 하루 전체)" / "→ store: 실행 기록 · 사용량(요금) 저장"
- 바꿈: "→ web: 한도 확인 + 예상 요금 잡아 두기 (방문자 · IP · 하루 · 달)" / "→ store: 실제 요금으로 정산, 실행 기록 저장"

**S4 · 4.3 재시도 항목** (P30)
- 지금: "**글자가 이미 화면에 나가기 시작했거나, 결제 · 한도 오류**"
- 바꿈: "**모델의 최종 답 글자가 이미 화면에 나가기 시작했거나, 결제 · 한도 오류**(… 등)면 다시 시도하지 않는다. '생각 중' · '차례 기다리는 중' 같은 진행 줄은 여기에 들지 않는다."

**S5 · 4.3 safety_identifier 항목** (P23)
- 지금: "모든 요청에 `safety_identifier` = 방문자 해시(64자)를 보낸다."
- 바꿈: "모든 요청에 `safety_identifier`를 보낸다. 값은 날마다 바뀌지 않는 해시 HMAC(비밀 소금, IP + 브라우저 임의 번호) 64자이고, 발표용은 고정값이다. 한도용 방문자 해시(날마다 바뀜)와 따로 둔다."

**S6 · 4.3 SDK 고정 항목** (P1)
- 지금: "`openai` SDK는 **3.14.0으로 고정**한다. Gradio와 함께 설치되는지 계획 3 전에 확인한다."
- 바꿈: "`openai` SDK는 **3.14.0으로 고정**한다. Gradio 6.27.0과 함께 설치 · 실행되는 것을 확인했다(2026-09-15). 설치 목록은 Space 빌드 마지막 단계가 판을 바꾸지 못하게 76개 판을 모두 고정한다(pydantic 2.12.5 포함)."

**S7 · 4.4 한도 표와 아래 문장** (P25)
- 표 요약 행 지금: "요약 | 없음 (장 전체를 한 번에) | 10만 | 1.6만 | 약 1,000원"
- 바꿈: "요약 | 없음 (장 전체를 한 번에) | 10만 (장마다 미리 센 토큰 수로 확인) | 3.2만 | 약 1,500원"
- 문장 지금: "요청 한 번의 `max_output_tokens`는 8,000으로 시작한다(요약은 16,000)."
- 바꿈: "요청 한 번의 `max_output_tokens`는 8,000으로 시작한다(요약은 32,000. OpenAI 권장 여유 2.5만보다 커야 끊긴 JSON에 요금만 내는 일을 막는다). 요약 입력 상한은 글자당 1토큰 추정을 쓰지 않는다(2023년치 제3장 요청이 11.3만 자라 막히지만 실제는 약 6.7만 토큰)."

**S8 · 5.2 요약** (P9 · P24 · P27 · P28 · P29)
- 지금: "미리 만들기: 2025년치 모든 장과 발표 시나리오에 들어가는 장."
- 바꿈: "요약 대상은 본문 장(제n장) 44개다. 부록과 장 밖 쪽은 요약하지 않는다(표 · 일지 위주이고, 2025년치 부록 조직도는 자료에 없음). 미리 만들기: 2025년치 제1~7장과 발표 시나리오에 들어가는 장."
- 지금: "가장 긴 장(2023년치 제3장, 108쪽)은 실측 약 7.1만 토큰으로"
- 바꿈: "가장 긴 장(2023년치 제3장, 108쪽)은 절별 JSON 입력으로 약 6.7만 토큰이라"
- 더함: "- 저장 기록에는 자료 지문(corpus_hash)과 근거 대조 결과를 함께 둔다. 대조기나 자료가 바뀌었을 때만 다시 대조한다."
- 더함: "- 처음 만드는 요약은 방문자가 창을 닫아도 끝까지 만들어 저장한다. 같은 장을 두 사람이 동시에 요청하면 한 번만 만든다."
- 더함: "- Flex 자리가 없으면(429 · 503) 30초~4분 간격으로 기다렸다 다시 하고, 그래도 안 되면 건너뛴다. 일반 요청으로 바꾸는 것은 명시할 때만이다."

**S9 · 6.1 Hugging Face Space** (P2 · P3 · P4 · P12 · P16)
- 지금: "비밀값(Secrets)은 `OPENAI_API_KEY`(**공개용 프로젝트** 열쇠)와 `PRESENTER_PASSWORD`다."
- 바꿈: "비밀값(Secrets)은 `OPENAI_API_KEY`(**공개용 프로젝트** 열쇠), `PRESENTER_PASSWORD`(20자 이상 무작위), `VISITOR_SALT`(방문자 해시용 40자 이상 무작위) 3개다. 공개돼도 되는 설정(Variables, 누구나 볼 수 있음)은 `STORE_DIR=/data`, `DAILY_BUDGET_KRW=4000`이다."
- 더함: "- Space README에 `sdk_version: 6.27.0`과 `python_version: \"3.12\"`를 적는다(기본 3.10이면 numpy 2.5.3이 설치되지 않음)."
- 더함: "- 배포는 허용 목록으로 만든 묶음을 저장소 밖에서 만들어 `hf upload`로 올린다. 저장소 폴더를 통째로 올리면 `.gitignore` 때문에 corpus가 빠진다."
- 더함: "- 화면 서버는 SSR · 모니터링 · 실행 기록 · 분석 전송을 끄고, 업로드는 1MB로 막는다. corpus는 Gradio 파일 허용 경로에 넣지 않는다."

**S10 · 6.1 잠들기 문장과 9 일정 9/27 행** (P35)
- 지금: "방문이 없으면 잠든다. 발표 30분 전에 열어 둔다."
- 바꿈: "48시간 방문이 없으면 잠든다. 코드를 올리거나 비밀값을 바꾸면 재시작되므로 9/26이 마지막 배포이고 9/27부터 동결한다. 9/27과 발표 30분 전에 주석님이 로그인한 상태로 열어 상태(Running / Sleeping / Paused)를 확인한다."
- 9장 9/27 행 지금: "여유일, 발표 리허설" → 바꿈: "배포 동결, 여유일, 발표 리허설(로그인해서 Space 상태 확인)"

**S11 · 6.2 화면 탭 줄** (P14)
- 지금: "[질문답변] [요약] [표 뽑기] [비교] [예시 모음]"
- 바꿈: "[질문답변] [예시 모음] [요약] [표 뽑기] [비교]" + 더함: "- 휴대폰 폭에서는 앞 탭 2개만 보이므로 0원 볼거리인 예시 모음을 둘째에 둔다."

**S12 · 6.2 근거 · 링크 · 안전 · 안내** (P8 · P11 · P33 · P34)
- 지금: "→ 외교부 원문 받으러 가기"
- 바꿈: "→ 외교부 원문 게시물" + 더함: "- 외교부 링크는 판마다 고정한다: `https://www.mofa.go.kr/www/brd/m_4105/view.do?seq=` 뒤에 2020년치 291, 2021년치 292, 2022년치 298, 2023년치 299, 2024년치 300, 2025년치 301."
- 더함: "- 짧은 구절은 화면에서 80자까지 보여 주고, 넘으면 줄인다."
- 더함: "- 모델 · 백서 · 방문자 글자는 모두 HTML 이스케이프해서 보여 준다. 모델 글에는 Markdown을 쓰지 않는다."
- 더함: "- 진행 과정 옆에 '멈추기' 버튼을 둔다."
- 더함: "- 화면에 이용 안내를 늘 둔다: AI가 만든 답이라는 알림, 모으는 정보와 보관 기간(질문 기록 30일), OpenAI(미국) 전송, 개인정보를 쓰지 말 것, 만 19세 미만은 보호자 동의, '문제 신고' 연락처, 외교부와 무관."

**S13 · 6.3 표 "2. 방문자" 행** (P16 · P17 · P19 · P20)
- 지금: "방문자는 IP + 브라우저 정보의 해시로 세고, 원래 IP는 저장하지 않는다"
- 바꿈: "방문자는 IP + 브라우저 정보(User-Agent, 언어, 브라우저에 저장한 임의 번호)를 비밀 소금으로 섞은 해시로 세고, 한국 날짜마다 바뀐다. 원래 IP는 저장하지 않는다. 한도 칸은 시작할 때 깎고, 0원이면서 OpenAI 혼잡 · 설정 오류로 끝난 실행만 돌려준다. 같은 IP는 하루 약 1,000원까지, 방문자당 동시에 1개, 시작 간격 10초다. 이 한도는 브라우저를 바꾸면 피할 수 있는 약한 한도이고, 진짜 방어는 1 · 3겹이다"

**S14 · 6.3 표 "3. 하루 전체" 행과 요금 계산 문단** (P18 · P19 · P21)
- 바꿈: "방문자 사용 합계가 하루 약 4,000원을 넘으면 다음 날까지 새 요청을 멈춘다. 시작할 때 예상 요금을 잡아 두고(질문 150원 · 새 요약은 장 크기로 계산 · 표 · 비교 1,000원) 끝나면 실제 요금으로 바꾼다. 발표용 비밀번호로 쓴 요금은 따로 센다"
- 요금 계산 문단에 더함: "  - 중간에 끊긴 요청은 사용량을 받지 못하므로 예상 요금과 실제 요금 중 큰 값으로 센다."

**S15 · 6.3 표에 새 행 (주석님 확인 필요)** (P22)
- 더함: "| 3-1. 한 달 전체 | 한국 달 기준 방문자 사용 합계가 약 12,600원($9)을 넘으면 방문자 새 요청을 멈춘다. 공개용 강제 한도($12)의 나머지를 발표용으로 남긴다 |"

**S16 · 6.3 표 "발표용 비밀번호" 행** (P21)
- 더함: "비밀번호는 20자 이상 무작위다. 같은 IP에서 5초에 1번 · 하루 20번까지 시도할 수 있고, 풀림은 그 창에만 3시간 간다."

**S17 · 7 문제 표에 새 행** (P6 · P8 · P9 · P13 · P23 · P35)
- "방문자가 '멈추기'를 누르거나 창을 닫음 | 질문답변은 다음 단계 전에 멈추고 상태 `cancelled`로 끝낸다. 주인 경보는 없고 한도 칸은 돌려주지 않는다. 처음 만드는 요약은 끝까지 만들어 저장한다"
- "대기 줄이 꽉 참 | '지금 붐벼요'라고 안내하고 한도는 깎지 않는다. 예시 모음으로 안내"
- "Storage Bucket 연결이 안 됨 | 메모리로만 한도를 센다(재시작하면 초기화). 예시 모음과 미리 만든 요약은 배포 묶음에서 보여 준다"
- "OpenAI가 방문자 식별값을 막음(identifier blocked) | 고정 안내를 보이고, 그 IP · 브라우저를 그날 멈춘다"
- "발표 중 45초 동안 진행 줄이 없음 | 같은 질문의 미리 돌려 둔 기록(쌍둥이)으로 넘어가는 버튼을 보인다"

**S18 · 8.1 LLM 없이 도는 시험에 더함** (P2 · P3 · P4 · P11 · P26)
- "- 화면 안전: 공격 문자열이 이스케이프되는지, `/gradio_api/file=corpus/pages.jsonl`이 403인지"
- "- 배포: Space README의 gradio 판 = 설치 목록 판, 배포 묶음에 `.env` · `data/` · `runs/`가 없고 corpus 10개가 있음"
- "- 요약 일감 설명서 지문 시험(바뀌면 판 번호를 올려야 통과), 한도 · 장부(동시 예약, 재시작, 자정, 끝나지 않은 실행)"

**S19 · 11 주석님이 직접 하실 일 2번**
- 지금: "**9/19 전: Hugging Face** 가입, PRO 구독"
- 바꿈: "**9/18까지: Hugging Face** 가입, PRO 구독(3D Secure 카드). 9/19에 로그인 승인, Bucket · Space 만들기, 비밀값 3개 입력(자세한 순서는 계획 3 사전 조사 기록 README 5장)"

**S20 · 12 확인 표** (P1 · P7 · P12)
- "`openai` 3.14.0(httpx2)과 Gradio(httpx) 함께 설치" 행 → "**확인 완료**: Gradio 6.27.0과 함께 설치 · 실행, 시험 174개 통과. Space 빌드의 pydantic 내림은 76줄 설치 목록으로 막음"
- "Gradio" 행 → "**확인 완료**: 일꾼 스레드 + 생성기로 실시간 표시, 멈추기, 탭, 파일 받기. 방문자 IP는 첫 배포 때 확인"
- "Hugging Face" 행 → "**확인 완료**: Protected, Secrets, Storage Bucket 볼륨. 마운트 쓰기 방식 · 프록시 IP 헤더는 첫 배포 때 확인"
- 마지막 항목 지금: "익명 공개 앱과 OpenAI 약관(지원 국가, 미성년자 동의)의 관계는 위험으로 기록만 해 둔다."
- 바꿈: "익명 공개 앱과 OpenAI 약관(지원 국가, 미성년자 동의)은 화면 이용 안내(6.2)로 알리고 위험으로 기록한다(강제할 수는 없음). 인공지능 기본법 제31조(미리 알리기 · 결과 표시)도 같은 안내와 'AI 생성' 표시로 따른다."

**S21 · 13 파일 배치** (P3 · P32)
- 더함: "├─ deploy/                Space 배포 묶음 만들기 (묶음은 저장소 밖에 만듦)"
- 더함: "├─ web/gallery/           예시 모음 (git 제외, 배포 묶음에만)"
- 지금: "corpus/ 준비 결과 (git 제외, 배포할 때 Space에 따로 올림)" → 바꿈: "corpus/ 준비 결과 (git 제외, 배포 묶음에 넣어 Protected Space에 올림)"

**S22 · 5 기능 머리 문단 (참고, 계획 3 필수는 아님)**
- 첫 실제 호출에서 질문 1번이 20~50원이었다. "질문답변 약 190~250원"은 정답지 시험 결과로 고치기로 이미 정해져 있다(`docs/research/2026-09-15-first-live-check.md`). 요약 1장 "약 300~600원"은 새 추정(보통 장 약 270원, 가장 큰 장 약 640원)과 맞다.

---

## 4. 아직 모르는 것

| # | 모르는 것 | 확인 방법 | 언제 |
|---|---|---|---|
| U1 | Hugging Face에서 방문자 IP가 어떻게 들어오는지(XFF 모양, `client.host`, `X-IP-Token` 유무, 가짜 XFF가 통하는지) | 발표용 비밀번호를 넣어야 보이는 임시 점검 칸: 값은 가리고 "XFF 있음 · 항목 수 · client.host가 가장 오른쪽과 같은지 · 공인/사설 · X-IP-Token 있음"만 표시. ① 평소 방문 ② PC에서 `curl -H "X-Forwarded-For: 1.2.3.4"` ③ 휴대폰 데이터로 방문. 규칙(P17)을 확정한 뒤 칸을 지움 | 첫 배포 직후, 약 15분 |
| U2 | Bucket 마운트 쓰기 방식(FUSE/NFS, 덮어쓰기 가능 여부), 앱 사용자 번호, 닫기 시간, 재시작 직전에 쓴 파일이 남는지 | 시작 때 점검 결과 한 줄(`STORE_SELFCHECK`)을 로그에서 읽음. 재시작 시험(주석님 승인) 전후 파일 수 비교 | 첫 배포 날 |
| U3 | HF 프록시가 수 분짜리 진행 스트림을 끊는지, 창 닫힘을 얼마나 빨리 알아채는지(heartbeat 15초) | 발표용 전용 **가짜 모델 5분짜리 실행**(0원)을 돌리고, 도중에 창을 닫아 멈춤 로그 시각을 봄. 느리면 `GRADIO_HEARTBEAT_INTERVAL`을 5초로 | 첫 배포 날 |
| U4 | Space 빌드가 여전히 requirements.txt 뒤에 `gradio[oauth,mcp]`를 까는지, Python 3.12 기반인지, SSR이 꺼졌는지 | 빌드 기록(`hf spaces logs <id> --build`)에서 pip 단계 · pydantic 판 · "SSR" 문구 확인 | 첫 배포 날 |
| U5 | Linux에서의 실제 메모리(예상 0.2~0.3GB) · 시작 시간 | Space 화면의 메트릭 | 첫 배포 날 |
| U6 | 요약의 추론 토큰 양(요금이 절반~2배로 달라짐), 걸리는 시간, Flex 대기 · 429 빈도, Flex + 스트림에서 `response.queued`가 오는지 | 첫 요약 점검: 2025년치 제7장 일반(약 55~110원) → 2023년치 제3장 Flex(약 260~450원). 요청별 사용량 · 첫 글자까지 시간 기록 → 요금 표 고침 | 요약 기능 완성 직후(주석님 승인) |
| U7 | 개발용 · 공개용 프로젝트가 `flex` 처리 방식을 허용하는지 | OpenAI 대시보드 프로젝트 설정 | 9/16 (주석님) |
| U8 | 요약 품질(문장 수 규칙, "~했다" 말투, 본문을 인용하는지) | 첫 요약 2~3개를 주석님이 읽음 | U6 직후 |
| U9 | 끊긴 스트림에서 이미 만든 출력도 청구되는지, "identifier blocked" 오류 모양, Flex 429의 오류 코드 | 문서에 없음 → 코드는 모르는 오류를 안전 쪽(칸 사용 · 예상 요금)으로 처리. 개발용 사용량 화면으로 가끔 대조 | 계획 3 내내 |
| U10 | Protected Space에서 로그아웃한 사람이 `huggingface.co/spaces/<id>`에서 무엇을 보는지, 로그를 볼 수 있는지, 익명 방문이 잠든 Space를 깨우는지(Sleeping / Paused) | 첫 배포 뒤 시크릿 창으로 확인. 발표 전에는 9/27 로그인 확인으로 대비 | 첫 배포 날 · 9/27 |
| U11 | OpenAI 강제 한도의 달 기준일 · 시간대 | OpenAI 대시보드 Limits 화면 | 9/16 (주석님) |
| U12 | 개인정보 보호법 개정본(2026-09-11 시행)의 해당 조문, 인공지능 기본법이 개인 포트폴리오에 적용되는지 | law.go.kr 원문 확인(Claude, 법률 자문 아님). 안내 문구는 보수적으로 둠 | 이용 안내 작업 때 |
| U13 | 빌드 시간 제한, PRO를 끊으면 Space가 어떻게 되는지, 한국 카드 해외 수수료 | 문서에 없음. 빌드는 흉내에서 약 3분이라 영향 작음. PRO 유지는 발표 뒤 결정 | 발표 뒤 |
| U14 | 다크 모드에서 글자 대비 | 화면 작업 때 브라우저 다크 모드로 스크린샷 | T4 |

---

## 5. 주석님이 직접 하실 일

계정 · 결제 · 열쇠 · 비밀값은 Claude가 대신할 수 없다. 열쇠와 비밀번호는 대화창에 붙여 넣지 않는다.

1. **9/16까지 — OpenAI 대시보드**
   - 개발용 · 공개용 프로젝트에서 처리 방식(service tier) `flex`가 허용인지 확인(개발용은 꼭).
   - 조직이 데이터 공유(학습에 쓰기)에 동의하지 않았는지 확인. 이용 안내에 "학습에 쓰지 않습니다"를 쓰려면 필요.
   - 공개용 강제 한도(약 $12)가 켜져 있는지, 달 기준일이 언제인지 확인.
   - 공개용 열쇠를 만들어 두기만 한다.
2. **9/16까지 — 정해 주실 것** (답만 주시면 됨)
   - '문제 신고 · 기록 삭제 요청' 연락처: 이메일 또는 GitHub Issues
   - 방문자 질문 기록 30일 보관(권장) / 보관 안 함
   - 달 단위 방문자 멈춤 12,600원(P22)을 넣을지
   - 탭 순서 [질문답변] [예시 모음] [요약] [표 뽑기] [비교]
   - 이용 안내 문구 초안(`digest.md` 부록 A) 승인
   - 3장 설계서 고칠 곳 S1~S22 승인
3. **9/18까지 — Hugging Face** 가입, 이메일 인증, PRO 구독($9. 신용카드는 3D Secure 지원 필요. 매달 1일 결제라 9월은 날짜만큼 청구). 영문 사용자 이름을 알려 주기(비밀 아님).
4. **9/19 — 로그인 승인**: 작업 T1이 끝난 뒤 터미널에서 `.venv/Scripts/hf.exe auth login` → 뜨는 주소를 브라우저로 열어 코드 입력 · 승인 → "logged in as <이름>" 확인.
5. **9/19 — Bucket 만들기**: huggingface.co/new-bucket, 이름 `whitepaper-store`, **Private**.
6. **9/19 — Space 만들기**: huggingface.co/new-space, 이름 `whitepaper-assistant`, SDK **Gradio**, 하드웨어 **CPU Basic**, 공개 범위 **Protected**.
7. **9/19 — 저장소 연결**: Space Settings > Storage Buckets에서 `whitepaper-store`를 `/data`에 읽기 · 쓰기로 연결.
8. **9/19 — 비밀값 · 설정값** (Settings > Variables and secrets, 웹 화면에서만 입력)
   - Secret 3개: `OPENAI_API_KEY`(공개용 열쇠), `PRESENTER_PASSWORD`(20자 이상 무작위), `VISITOR_SALT`(40자 이상 무작위)
   - Variable 2개: `STORE_DIR=/data`, `DAILY_BUDGET_KRW=4000` (Variables는 누구나 볼 수 있음)
   - 저장한 비밀값이 다시 안 보이는 것은 정상.
9. **9/19~20 — 첫 배포 승인**: Claude가 "파일 N개, 약 16MB를 올려도 될까요?"라고 여쭈면 확인 후 답.
10. **첫 배포 직후(약 15분)** — 로그인하지 않은 시크릿 창에서 `https://<이름>-whitepaper-assistant.hf.space` 열기 → 예시 1개 · 질문 1개. Claude가 준비한 IP 점검 3단계(평소 · curl · 휴대폰 데이터) 따라 하기.
11. **요약 기능 완성 직후** — 첫 요약 점검 승인(약 300~550원), 요약 2~3개를 읽고 말투 · 문장 수 의견 주기.
12. **첫 배포 다음 날** — Hugging Face Billing에 추가 요금이 0인지, OpenAI 공개용 사용액이 예상 안인지 확인.
13. **9/26까지** — 예시 모음과 발표 질문 쌍둥이 기록을 한 건씩 보고 승인. 미리 만든 요약 업로드 승인.
14. **9/27** — 동결 시작. 로그인해서 Space 상태 확인(Paused면 Settings에서 재시작), 발표 질문 리허설(비밀번호).
15. **발표 날** — 30분 전에 열기. 휴대폰 핫스팟 · 노트북 준비. 비밀번호는 가려진 칸에만 입력. 설정 · 대시보드 화면은 띄우지 않기.
16. **발표 뒤** — PRO 유지 여부 결정(끊으면 Space가 어떻게 되는지는 문서에 없음).

---

## 6. 계획 3 작업 목록 (안)

| 작업 | 만드는 것 | 먼저 끝나야 할 것 | 크기 |
|---|---|---|---|
| T1 설치 목록 맞추기 | `requirements.txt`(76줄, P1), `requirements-prep.txt`, `.venv` 재설치(hf 명령 포함), 전체 시험 통과 기록 | — | 작음 (1시간) |
| T2 조수 고치기 (0원 시험) | `run(..., should_stop=)` + `cancelled` 상태 · 경보 없는 안내(P8); 이벤트 `t` · 기록 판 2 · moderation 분류(P10); `turn()`: 빈 도구 키 생략 · `service_tier` · `prompt_cache_options` · `timeout_s` · `on_text`(P25 · P31); "화면에 나감" 기준(P30) | T1 | 중간 (반나절) |
| T3 저장 · 한도 `store/` | 한국 날짜, 방문자 · IP · 안전 키(P16 · P23); 예약 · 정산 · 돌려주기 · IP 원 상한 · 발표용 따로 · 달 멈춤 · 오래된 예약 풀기 · 동시 1개 · 10초(P18~P22); 쓰기 스레드 · 되살리기 · 날 합계 · 30일 삭제 · self-check 스레드 · degraded(P6 · P34). 시험: 동시 예약, 재시작, 깨진 파일, 자정, 끝나지 않은 실행, 비밀번호 시도 제한 | T1 | 큼 (하루) |
| T4 화면 뼈대 + 질문답변 탭 (`web/`, `app.py`) | 서버 설정(P12 · P13), 일꾼 다리 · tick · 멈춤 3길(P7 · P8), 그리기(esc · 배지 · 참조 · 80자 · 외교부 링크 · AI 생성, P11 · P33), IP 규칙(P17), 비밀번호(P21), 이용 안내(P34), 글꼴 · 탭 순서(P14). 시험: 공격 문자열, `/gradio_api/file=corpus/...` 403, private 이벤트도 한도 검사, 가짜 모델로 진행 순서 · 창 닫힘 · 멈추기 | T2, T3 | 큼 (하루) |
| T5 요약 기능 | 장 목록(44장 + 미리 센 토큰), 형식 B 입력, 스키마 · 설명서 · 지문 시험, 대조 펴기 · 묶기 · 절 비교(P24~P27), 저장 · 찾기(Bucket → 묶음) · 대조 결과 저장(P28), 분리 일꾼 · 장 잠금(P9), 진행 줄 파서 · 요약 탭(P31) | T2, T3, T4 | 큼 (하루) |
| T6 요약 미리 만들기 명령 + 첫 요약 점검 | Flex 명령(재시도 규칙 · `--fallback-standard` · 80% 표시, P29), 점검 기록 `docs/research/`, 요금 표 고침(U6) | T5, 주석님 승인(U7 · 할 일 11) | 중간 (2시간 + 실행) |
| T7 예시 모음 | 기록 → 항목 변환 도구, 재생기, 예시 모음 탭, 45초 감시 · 쌍둥이 버튼(P32 · P35) | T2, T4 | 중간 (반나절) |
| T8 배포 도구 | `deploy/build_space_bundle.py`(허용 목록 · 저장소 밖 · 열쇠 모양 거부 · 필수 파일 · README 틀, P2 · P3), 시험 | T1, T4 | 작음~중간 (2시간) |
| T9 첫 배포와 점검 | 업로드(승인), 빌드 기록 · SSR 꺼짐(U4), STORE_SELFCHECK(U2), IP 점검(U1), 가짜 긴 실행(U3), 시크릿 창(U10), 재시작 시험, `docs/research/` 기록 · 에러노트 | T8, 주석님 할 일 3~8 | 중간 (2~3시간) |
| T10 설계서 반영 · 발표 절차 | 3장 S1~S22 반영(승인 뒤), 발표 운영 절차 문서(P35) | T9 | 작음 |

- 제안 일정: 9/16 T1~T3 · 9/17 T4 · 9/18 T5 · 9/19 T6 · T8 · 9/19~20 T9 · 9/20~21 T7 · T10. 표 뽑기 · 비교(설계서 9장 9/21~23)는 다음 계획에서 P15(CSV)를 쓴다.
- 요금이 드는 단계는 T6(첫 요약 점검)과 T9(질문 1~2개)뿐이다. 나머지는 가짜 모델로 시험한다.

---

## 7. 파일

모든 경로는 `docs/research/2026-09-15-plan3-groundwork/` 기준. 아래 표가 저장소에 옮긴 파일 전부다(217개, 약 1.1MB).

| 경로 | 내용 |
|---|---|
| `README.md`, `digest.md` | 이 요약, 영어 근거 모음(결정별 증거 · 틀림 · 불확실 · 설계서 변경 근거 · 이용 안내 초안) |
| `gradio-ui/proto/bridge.py`, `gradio-ui/proto/render.py`, `gradio-ui/proto/app.py`, `gradio-ui/proto/slow_fake.py`, `gradio-ui/proto/make_example.py` | 일꾼 다리 · 멈춤 · 이스케이프 그리기 · 가짜 느린 모델 시제품 (T4 참고) |
| `gradio-ui/proto/sse_client.py`, `gradio-ui/proto/probe_misc.py`, `gradio-ui/proto/probe_defaults.py`, `gradio-ui/proto/xss_lab.py`, `gradio-ui/proto/xss_lab2.py` | 스트림 · 멈춤 · 대기 줄 · 기본 노출 · XSS 실험 스크립트 |
| `gradio-ui/proto/measurements/*` (46개) | 측정 원본: 스트림 지연, 창 닫힘, 멈추기, 동시 4, 대기 줄 503, private 이벤트, 기본 노출, 비밀번호, 가짜 모델 실행 기록 |
| `gradio-ui/pip-freeze.txt` | 시제품 설치 판 |
| `gradio-ui-verify/verify.md`, `gradio-ui-verify/freeze.txt` | 검증 기록, 검증 환경 설치 판 |
| `hf-spaces/build_space_bundle.py` | 허용 목록 배포 묶음 시제품(T8에서 고쳐 옮김: 저장소 밖, 단어 경계) |
| `hf-spaces/space_template/README.md` | Space README 틀 |
| `hf-spaces/store_selfcheck.py`, `hf-spaces/store_selfcheck_local_output.txt`, `hf-spaces/usage_ledger_sketch.py`, `hf-spaces/usage_ledger_output.json` | 저장소 점검, 사용량 장부 시제품(장부는 발표용 섞임 · 예약 없음 결함) — 참고용 |
| `hf-spaces/startup_probe.py`, `hf-spaces/startup_probe_output*.json` (2개), `hf-spaces/startup_probe_stderr.txt`, `hf-spaces/real_repo_dryrun.json`, `hf-spaces/fake_bundle_run*.json` (2개), `hf-spaces/deps/*` (2개) | 시작 시간 · 메모리, 묶음 모의 실행, Linux 해석(3.10 실패 기록) |
| `hf-spaces-verify/verify.md`, `hf-spaces-verify/gradio_probe/*` (3개), `hf-spaces-verify/ledger_recheck.py`, `hf-spaces-verify/ledger_recheck_output.json`, `hf-spaces-verify/*_rerun.json` (2개) | 검증 기록, 파일 403 · IP 실험, 장부 반례 |
| `hf-spaces-verify/deps/lock*.txt` (4개) | 검증의 Python 판별 Linux 잠금 해석(3.10 · 3.12 · 3.13) |
| `deps/requirements-space.txt` | 55줄 잠금(P1의 바탕) |
| `deps-verify/requirements-space-with-step4.txt` | **76줄 잠금 — P1에서 쓸 파일** (중요) |
| `deps/emul_*_after*.txt` (6개), `deps/emul_*_log.txt` (2개), `deps-verify/v3_*.txt` (3개), `deps-verify/uv_checks.txt`, `deps/lock-*.txt` (6개), `deps-verify/lock*.txt` (5개), `deps-verify/req_norm.txt`, `deps/reqA-freeze-pins.txt`, `deps/reqB-body.txt`, `deps/python_version_check.txt` | Space 빌드 흉내 결과, Linux 잠금 확인 (판을 바꿀 때 다시 돌림) |
| `deps/smoke_*` (8개), `deps-verify/smoke/*` (13개) | 한 프로그램에서 Gradio + OpenAI, SSR · IP 헤더 실험 |
| `deps/footprint_*` (4개), `deps/memwin.py`, `deps/search_latency.*` (2개), `deps-verify/foot/*` (5개) | 메모리 · 시간 측정 |
| `deps/pytest_run*.txt` (5개), `deps-verify/pytest_*.txt` (3개) | 시험 결과(174 통과) |
| `deps/space-README-header.yml`, `deps-verify/verify.md` | README 머리 초안, 검증 기록 |
| `deps/deps_graph.*` (2개), `deps/file_collisions.*` (2개), `deps/freeze.txt`, `deps/install_log.txt`, `deps/httpx2_client_check.txt`, `deps-verify/file_collisions_verify.txt`, `deps-verify/pypi_*` (3개), `deps-verify/v1_*.txt` (2개), `deps-verify/v2_*.txt` (2개) | 의존 관계 · 파일 겹침 · PyPI 최신 판 확인, 설치 기록 |
| `summary/summary_proto.py` | 요약 설명서 · 스키마 · 입력 만들기 · 대조 펴기 시제품(`storage_key()`는 틀림, P28) |
| `summary/chapters.json`, `summary/chapters.md`, `summary/chapter_sizes.py` | 44장 크기 표(쪽 · 글자 · 토큰 · 예상 요금) |
| `summary/summary_costs*` (2개), `summary/sdk_request_shape_check*` (2개), `summary/verify_summary_check*` (2개), `summary/progress_proto*` (2개) | 요금 계산, 요청 모양, 대조, 진행 줄 파서 |
| `summary-verify/verify.md`, `summary-verify/recount*` (2개), `summary-verify/verify_recheck*` (2개), `summary-verify/timing_recheck*` (2개), `summary-verify/wire_recheck*` (2개), `summary-verify/cost_recheck_output.txt` | 검증 기록과 재실험(재집계, 대조 시간, 재시도 반례) |
| `limits-store-safety/limits_store.py`, `limits-store-safety/test_limits_store.py`, `limits-store-safety/limits_store_results.json` | 한도 · 장부 시제품과 시험(검증 결함은 P18~P21로 고칠 것) |
| `limits-store-safety/replay_prototype.py`, `limits-store-safety/replay_results.json`, `limits-store-safety/render_safety.py` | 재생기, 안전 그리기 · CSV |
| `limits-store-safety/html2text.py`, `limits-store-safety/install_log.txt`, `limits-store-safety/pip-freeze.txt` | 문서 사본을 글자로 바꾸는 도구, 설치 기록 |
| `limits-store-safety-verify/verify.md`, `limits-store-safety-verify/rerun/*` (8개), `limits-store-safety-verify/gr_html_template_check_output.txt`, `limits-store-safety-verify/resolve_log.txt` | 검증 기록, 한도 반례(`adversarial_limits.*`)와 시제품 재실행 사본, gr.HTML 템플릿 실행 실험 결과 |

- **옮기지 않은 것과 이유** (원본은 이 PC의 임시 작업 폴더에만 있음): 가상 환경 · 설치 캐시(`venv` · `venv2` · `venv312` · `.venv` · `deps/emul_A` · `deps/emul_B` · `deps-verify/v1`~`v3` · `uv_cache` · `wheels` · `wheel` · `__pycache__`, 용량) / 저장소 코드 사본(`deps/repo_copy`, `deps-verify/copy_prep` · `copy_noprep`, `gradio-ui/proto/assistant` · `tests`, 저장소에 이미 있음) / Gradio 소스 사본(`limits-store-safety/src/`) · 문서 사본(`hf-spaces/refs/`, `limits-store-safety/pages/`, `limits-store-safety-verify/pages/`, 저작권) / 실험용 자료 사본(`gradio-ui/proto/_corpus` · `_downloads`, `hf-spaces-verify/gradio_probe/corpus/` · `fake.env`) / 검증용 앱 폴더 `gradio-ui-verify/v/`(옮길 폴더 규칙에서 `v` 이름 폴더는 뺌. 결과는 `gradio-ui-verify/verify.md`에 있음) / 300KB 넘는 파일 2개(`gradio-ui-verify/gradio.json` 1.04MB, `limits-store-safety-verify/resolve_report.json` 742KB) / 허용 확장자(.md .py .json .jsonl .txt .csv .toml .yaml .yml .ini)가 아닌 파일 36개(`.log` 23 · `.in` 9 · `.sh` · `.patch` · `.js` · `.err`, 예: `deps/emulate_space_build.sh`, `limits-store-safety/runner_timestamps.patch`, `limits-store-safety-verify/gr_html_template_check.js`, `deps/compile-py3.*.log`) / `hf-spaces/space_template/requirements.txt`(4줄 목록은 쓰지 말 것 — P1의 76줄로 대체).
- **저작권 때문에 올리지 않음**: 없음. 옮긴 파일 전부를 백서 쪽 글(`corpus/pages.jsonl`, 공백 제거)과 대조해 40자 이상 이어서 같은 곳을 찾았는데(JSON 이스케이프를 푼 글도 대조) 걸린 파일이 0개였다.
- **열쇠 검사**: `sk-` + 20자 이상, `OPENAI_API_KEY=` + 값, 30자 이상 `hf_` 토큰, 개인 키 블록 — 남은 것 없음. `deps/footprint_step.py` · `deps/smoke_app.py`의 가짜 열쇠 글자(요청에 쓰지 않음)는 검사에 걸리지 않게 `sk-fake-never-used`로 바꿨다.
