# V3.2.1 Historical Data Acquisition Phase 4.1

## 목적
2026년 KRX 로그인 정책에 맞춰 pykrx 수집을 장시간 실행하기 전에 인증/세션을 먼저 검증한다.

## KRX 자격증명 저장 위치
프로젝트 루트 `C:\dev\stock-analytics\.env`에만 저장한다.

```env
KRX_ID=
KRX_PW=
```

`.env`는 Git 대상에서 제외되며 ZIP에도 포함시키지 않는다. 배포용 `.env.example`에는 빈 키만 둔다.

## 1. pykrx 업데이트
```bat
python -m pip install --upgrade -r requirements.txt
```

## 2. 인증 사전검사
```bat
python -m src.main krx-provider-check-v321 --code 005930 --end 20260709
```

PASS가 확인된 경우에만 전체 수집을 실행한다. 실패하면 장시간 ticker loop를 시작하지 않는다.

## 3. 과거 valuation 수집
```bat
python -m src.main acquire-historical-data-v321 --universe-csv config\universe_kr_24.example.csv --start 20200101 --end 20260709 --frequency m --output-dir data\raw\v321
```

## 안전 규칙
- KRX_ID/KRX_PW 값은 출력하지 않는다.
- 2026-07-09 이후 자료를 V3.2.1 연구 입력으로 수집하지 않는다.
- 수정주가를 total return으로 승격하지 않는다.
- 현재 valuation을 과거로 역채움하지 않는다.
- provider preflight 실패 시 즉시 종료한다.
