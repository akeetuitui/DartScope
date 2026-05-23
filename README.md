# DartScope

DartScope는 특정 기업의 특정 사업연도 사업보고서를 DART Open API로 조회하고, 전체 재무제표에서 주요 재무지표를 계산하는 도구입니다.

현재는 로컬 실행 버전입니다. CLI, 로컬 웹사이트, 텔레그램 봇으로 사용할 수 있습니다.

## 준비

1. DART Open API 인증키를 발급받습니다.
2. 터미널에서 인증키를 환경변수로 설정합니다.

```bash
export DART_API_KEY="발급받은_인증키"
```

웹/텔레그램 기능에 필요한 패키지는 아래처럼 설치합니다.

```bash
python3 -m pip install -r requirements.txt
```

## CLI 사용법

```bash
./dartscope 삼성전자 2024
./dartscope 005930 2024 --fs-div CFS
./dartscope 삼성전자 2024 --csv outputs/samsung_2024.csv
./dartscope 삼성전자 2024 --unit million
```

개발용 JSON으로 보고 싶으면 아래처럼 실행합니다.

```bash
./dartscope 삼성전자 2024 --format json
```

`--fs-div`는 재무제표 구분입니다.

- `CFS`: 연결재무제표
- `OFS`: 별도재무제표

기업명으로 처음 조회할 때는 DART 기업코드 목록을 `.dart_cache/corp_codes.xml`에 저장합니다. 기업코드 캐시를 새로 받으려면 아래 옵션을 붙입니다.

```bash
./dartscope 삼성전자 2024 --refresh-corp-codes
```

## 웹사이트 로컬 실행

```bash
uvicorn web_app:app --reload
```

브라우저에서 아래 주소로 접속합니다.

```text
http://127.0.0.1:8000
```

화면에서 기업명 또는 종목코드, 여러 사업연도, 연결/별도 구분, 금액 단위를 입력하면 주요 재무지표가 연도별 비교 표로 표시됩니다. 사업연도는 `2022 2023 2024`처럼 공백으로 구분하거나 `2022,2023,2024`처럼 쉼표로 구분할 수 있습니다. 금액 단위는 원, 천원, 백만원, 억원, 조원 중 선택할 수 있습니다.

## 텔레그램 봇 로컬 실행

1. 텔레그램 BotFather에서 봇을 만들고 토큰을 발급받습니다.
2. 터미널에서 봇 토큰을 환경변수로 설정합니다.

```bash
export TELEGRAM_BOT_TOKEN="발급받은_텔레그램_봇_토큰"
python3 telegram_bot.py
```

텔레그램에서 봇에게 아래처럼 메시지를 보내면 됩니다.

```text
삼성전자 2024
삼성전자 2022 2023 2024
삼성전자 2022 2023 2024 단위 백만원
삼성전자 2024 단위 조원
삼성전자 2024 텍스트
/report 삼성전자 2024
/business 삼성전자 2024
/mac
```

봇 명령어는 `/start`, `/help`, `/mac`, `/report`, `/business`를 지원합니다. 일반 메시지는 기업명, 사업연도, 선택 단위, `텍스트` 요청을 해석합니다. 봇은 연결재무제표 기준으로 매출액, 영업이익, 영업이익률, 당기순이익, 부채비율, ROE, ROA를 답장합니다. 여러 연도를 보내면 연도별 비교 형태로 답장합니다.

## 추출 지표

재무제표 원장에서 아래 값을 찾고 지표를 계산합니다.

- 자산총계
- 부채총계
- 자본총계
- 유동자산
- 유동부채
- 현금및현금성자산
- 매출액
- 매출원가
- 매출총이익
- 판매비와관리비
- 영업이익
- 법인세차감전순이익
- 당기순이익
- 법인세비용
- 기본주당이익
- 영업활동현금흐름
- 매출총이익률
- 매출원가율
- 판관비율
- 부채비율
- 유동비율
- 영업이익률
- 순이익률
- ROE
- ROA

2022년 이후 사업연도는 DART가 제공하는 주요 재무지표 API도 함께 조회할 수 있습니다.

```bash
./dartscope 삼성전자 2024 --include-dart-indicators
```

## GitHub 공개 전 확인

공개 저장소에 올리기 전에 아래 파일만 커밋 대상인지 확인합니다.

```bash
git status --short
```

API 키, `.env`, `.dart_cache/`, `outputs/`, `__pycache__/`는 올리지 않습니다.

GitHub 웹사이트에서 공개 저장소 `DartScope`를 만든 뒤, 터미널에서 아래처럼 연결합니다.

```bash
git remote add origin https://github.com/사용자명/DartScope.git
git add .gitignore README.md dart_financials.py dartscope web_app.py telegram_bot.py requirements.txt
git commit -m "Initial DartScope release"
git push -u origin master
```

## 사업보고서 텍스트 추출

CLI에서는 아래처럼 사업보고서 원문에서 주요 텍스트 섹션을 함께 가져올 수 있습니다.

```bash
./dartscope 삼성전자 2024 --include-text --format json
```

웹에서는 조회 결과 아래에 최신 입력 연도 기준 사업보고서 주요 텍스트를 함께 보여줍니다.

- 회사의 개요
- 사업의 내용
- 사업의 개요
- 주요 제품 및 서비스
- 매출 및 수주상황
- 연구개발활동
- 위험관리
- 향후 추진하려는 신규사업
- 이사의 경영진단 및 분석의견

OpenDART 공시검색 API로 사업보고서 접수번호를 찾고, 공시서류 원문파일 API로 XML 원문을 받아 텍스트를 추출합니다.

## 참고한 공식 API

- 기업 고유번호: `https://opendart.fss.or.kr/api/corpCode.xml`
- 단일회사 전체 재무제표: `https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json`
- 단일회사 주요 재무지표: `https://opendart.fss.or.kr/api/fnlttSinglIndx.json`

## 텔레그램 봇 배포

텔레그램 봇은 서버에서 계속 실행되는 worker 프로세스로 배포합니다. 배포 서버에는 아래 환경변수 두 개를 설정해야 합니다.

```text
DART_API_KEY
TELEGRAM_BOT_TOKEN
```

토큰과 API 키는 GitHub에 올리지 말고, 배포 서비스의 Environment Variables 또는 Secrets 메뉴에만 입력합니다.

### Render 배포 예시

1. Render에서 새 `Background Worker`를 만듭니다.
2. GitHub 저장소 `akeetuitui/DartScope`를 연결합니다.
3. Build Command는 아래처럼 설정합니다.

```bash
pip install -r requirements.txt
```

4. Start Command는 아래처럼 설정합니다.

```bash
python telegram_bot.py
```

5. Environment Variables에 `DART_API_KEY`, `TELEGRAM_BOT_TOKEN`을 추가합니다.
6. Deploy를 누릅니다.

`render.yaml`도 포함되어 있으므로 Render Blueprint 방식으로도 worker를 만들 수 있습니다.

### 로컬에서 봇 실행

```bash
export DART_API_KEY="발급받은_DART_API_키"
export TELEGRAM_BOT_TOKEN="발급받은_텔레그램_봇_토큰"
python telegram_bot.py
```

실행 중인 터미널에 로그가 보이는 것은 정상입니다. 봇이 꺼지지 않고 메시지를 기다리는 상태입니다. 멈추려면 `Control + C`를 누릅니다.

## Google Cloud Run 웹 배포

Google AI Studio의 Build/Deploy 흐름은 앱을 Google Cloud Run 같은 Google Cloud 런타임으로 배포하는 방식입니다. DartScope 웹앱은 FastAPI 앱이므로 Cloud Run 배포용 `Dockerfile`을 포함합니다.

배포에 필요한 파일은 아래입니다.

```text
Dockerfile
.dockerignore
requirements.txt
dart_financials.py
web_app.py
```

배포 환경변수에는 아래 값을 설정합니다.

```text
DART_API_KEY
```

Cloud Run에서 컨테이너는 `PORT` 환경변수로 전달된 포트에 바인딩해야 하므로, Dockerfile은 아래 명령으로 웹앱을 실행합니다.

```bash
uvicorn web_app:app --host 0.0.0.0 --port ${PORT:-8080}
```

텔레그램 봇 배포 파일(`telegram_bot.py`, `Procfile`, `render.yaml`)은 웹 배포에는 필요하지 않습니다.
