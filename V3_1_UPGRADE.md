# Stock Analytics V3.1

## 구현 범위

- V3의 `research_seen_through`와 봉인 레지스트리를 그대로 상속
- 53개 후보: 재무·모멘텀 단독, 공시 이벤트형 재무, 고정비중·국면동적 앙상블
- 겹치지 않는 20거래일 IC, 리밸런싱 IC, 부트스트랩 95% 신뢰구간
- 폴드별 동일 유니버스·KODEX 200 동시 초과 여부
- 장기 고정 보유, 반복 손실, 편입·유지·제외 보고
- 종목·업종 집중도, HHI, 개별 종목 최악 기여도 경고
- 기여도 보고서의 `entry_close` 및 선택적 종목명 출력
- 외부 총수익지수와 시점별 유니버스 원자료의 완전성 감사
- 실제 주문 기능 없음

## 설치·테스트

```bat
cd C:\dev\stock-analytics
.venv312\Scripts\activate
pip install -r requirements-lock.txt
set PYTHONWARNINGS=error
python -m pytest -q
```

## 첫 실행

기존 V3 연구 컷오프 뒤의 신규 미래자료가 아직 충분하지 않으므로
`--lockbox-start`를 넣지 않습니다.

```bat
python -m src.main ml-diagnose-v31 --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --min-train-days 504 --fold-days 126 --commission 0.015 --tax 0.18 --slippage 0.05 --rank-scope market --output-prefix ml_v31_h20
```

`기존 공개 시험기간`은 연구 참고용입니다. V3의 2026년 1~7월 결과를 신규 봉인시험으로
재분류하지 않습니다.

## 검증 원자료를 갖춘 실행

템플릿을 복사해 출처가 확인된 전체 관측기간 자료로 채운 후 실행합니다.

```bat
python -m src.main ml-diagnose-v31 --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --min-train-days 504 --fold-days 126 --commission 0.015 --tax 0.18 --slippage 0.05 --universe-history-csv config\universe_history_v3.csv --total-return-csv config\total_return_history.csv --security-master-csv config\security_master.csv --rank-scope market --output-prefix ml_v31_h20
```

`total_return_index`는 분할·증자·배당·ETF 분배금을 반영한 검증 가능한 누적
총수익지수여야 합니다. 일부 날짜나 일부 종목만 채우면 총수익률 검증은 통과하지 않습니다.

## 강화된 승인 조건

V3.1은 전체 워크포워드 누적 양수만으로 통과시키지 않습니다. 다수 폴드에서 두
벤치마크를 동시에 이기고, 비중첩 IC 신뢰구간 하한이 양수이며, 순위 단조성·집중도·
시점별 유니버스·총수익률·새 미래 봉인시험을 모두 통과해야 `ADOPT`가 됩니다.

현재는 `RESEARCH_ONLY`와 `daily-shadow`만 허용하며 실제 주문 연결은 금지합니다.
