# Stock Analytics V3 업그레이드

## 설치 후 확인

```bat
cd C:\dev\stock-analytics
.venv312\Scripts\activate
pip install -r requirements-lock.txt
set PYTHONWARNINGS=error
python -m pytest -q
```

정상 기준은 `33 passed`입니다.

## 첫 V3 연구 실행

현재 보유한 데이터는 이미 분석에 노출됐으므로 첫 실행에서는 새 봉인기간을 등록하지
않습니다.

```bat
python -m src.main ml-diagnose-v3 --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --min-train-days 504 --fold-days 126 --commission 0.015 --tax 0.18 --slippage 0.05 --rank-scope market --output-prefix ml_v3_h20
```

이 실행이 현재 라벨의 마지막 날짜를 `research_seen_through`로 기록합니다. V2에서 이미
확인한 `20260105` 이후 기간은 V3의 새 봉인시험으로 인정하지 않습니다.

## 시점별 유니버스

`config\universe_history_v3.template.csv`를 복사해
`config\universe_history_v3.csv`를 작성합니다. 모든 종목의 전체 관측기간을 실제 당시
구성표와 출처로 덮어야 검증 완료가 됩니다.

## 미래 봉인시험

연구 컷오프 뒤의 시작일부터 20거래일 라벨이 충분히 쌓인 후에만 아래 명령을 한 번
실행합니다.

```bat
python -m src.main ml-diagnose-v3 --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --min-train-days 504 --fold-days 126 --commission 0.015 --tax 0.18 --slippage 0.05 --lockbox-start YYYYMMDD --universe-history-csv config\universe_history_v3.csv --rank-scope market --output-prefix ml_v3_h20
```

등록된 V3 봉인 시작일은 변경할 수 없습니다.

## 안전 상태

- `daily-shadow`: 계속 실행
- V3 예측: 연구 결과로만 저장
- 실주문: 연결 금지
- 뉴스 감성분석: 보류
- 기존 `.env`, DB, 수집 데이터와 모델: ZIP에 포함되지 않으며 덮어쓰지 않음
