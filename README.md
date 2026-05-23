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

화면에서 기업명 또는 종목코드, 여러 사업연도, 연결/별도 구분을 입력하면 주요 재무지표가 연도별 비교 표로 표시됩니다. 사업연도는 `2022 2023 2024`처럼 공백으로 구분하거나 `2022,2023,2024`처럼 쉼표로 구분할 수 있습니다.

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
```

봇은 연결재무제표 기준으로 매출액, 영업이익, 영업이익률, 당기순이익, 부채비율, ROE, ROA를 답장합니다. 여러 연도를 보내면 연도별 비교 형태로 답장합니다.

## 추출 지표

재무제표 원장에서 아래 값을 찾고 지표를 계산합니다.

- 자산총계
- 부채총계
- 자본총계
- 유동자산
- 유동부채
- 현금및현금성자산
- 매출액
- 매출총이익
- 영업이익
- 법인세차감전순이익
- 당기순이익
- 영업활동현금흐름
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

## 참고한 공식 API

- 기업 고유번호: `https://opendart.fss.or.kr/api/corpCode.xml`
- 단일회사 전체 재무제표: `https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json`
- 단일회사 주요 재무지표: `https://opendart.fss.or.kr/api/fnlttSinglIndx.json`
