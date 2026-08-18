# V3.2: Point-in-Time Foundation and Champion-Challenger

V3.2는 V3.1을 삭제하거나 덮어쓰지 않습니다. `v31_champion`을 동결된 Champion으로
보존하고, 사전에 고정한 4개 Challenger만 과거 내부 폴드에서 비교합니다.

## 핵심 변경

- 모델 선택과 최종 검증을 분리한 중첩 시계열 평가
- 모든 내부 폴드에 horizon 이상의 purge/embargo 적용
- V3.1 Champion과 V3.2 Challenger를 같은 비용·기간으로 나란히 출력
- 재무 품질 적격 필터와 모멘텀·변동성 진입 신호 분리
- 연속 손실 2회 종목을 다음 리밸런싱에서 제외하는 선택적 loss guard
- 종목당 15%, 업종당 40% 상한과 시장 국면별 현금 비중
- 점수 간격이 작을 때 5종목 대신 최대 8종목으로 분산
- 시점별 유니버스·총수익률·재무 공시일·기업행사 입력을 별도 감사
- 12개 이상의 비중첩 검증기간 요구
- Challenger 실패 시 V3.1 유지, 전체 실패 시 동일가중/ETF 그림자 비교로 후퇴
- 실제 주문 기능 없음

## 첫 실행

기존에 결과를 본 `2026-01-05~2026-07-09`를 새 봉인시험으로 등록하지 않습니다.
따라서 첫 실행에는 `--lockbox-start`를 넣지 않습니다.

```bat
python -m src.main ml-diagnose-v32 --horizon 20 --benchmark-code 069500 --validation-days 252 --test-days 126 --min-train-days 504 --fold-days 126 --embargo-days 20 --commission 0.015 --tax 0.18 --slippage 0.05 --stock-cap 0.15 --industry-cap 0.40 --rank-scope market --output-prefix ml_v32_h20
```

원자료가 준비된 뒤에는 다음 입력을 추가합니다.

```bat
python -m src.main ml-diagnose-v32 --horizon 20 --benchmark-code 069500 --validation-days 252 --test-days 126 --min-train-days 504 --fold-days 126 --embargo-days 20 --commission 0.015 --tax 0.18 --slippage 0.05 --stock-cap 0.15 --industry-cap 0.40 --universe-history-csv config\universe_history_v3.csv --total-return-csv config\total_return_history.csv --security-master-csv config\security_master.csv --corporate-actions-csv config\corporate_actions.csv --rank-scope market --output-prefix ml_v32_h20
```

템플릿 파일은 형식 예시일 뿐입니다. 예시 값을 실제 데이터로 오인해 사용하지 마세요.

## 판정 원칙

`ADOPT`는 20개 기준을 모두 충족할 때만 표시됩니다. 원자료가 없거나 새 미래 봉인시험이
아니면 정상적으로 `RESEARCH_ONLY`가 유지됩니다. V3.2 결과가 V3.1보다 낮아도 Champion은
자동 교체되지 않습니다.

## 주요 출력

- `_nested_model_selection.csv`: 검증기간을 보지 않은 내부 후보 비교
- `_candidate_manifest.csv`: 사전에 고정된 Champion·Challenger 설정
- `_purge_embargo_audit.csv`: 폴드별 누출·간격 감사
- `_champion_challenger.csv`: V3.1과 선택 Challenger 비교
- `_financial_pit_audit.csv`: 재무 공시일·가치지표 관측일 감사
- `_corporate_action_audit.csv`: 기업행사 입력 유효성
- `_portfolio_periods.csv`: 시장국면·현금비중·점수 간격
- `_portfolio_risk.csv`: 종목·업종 집중도와 HHI
- `_fallback_policy.json`: 실패 시 후퇴 규칙
- `_verdict.json`: 전체 판정과 연구 컷오프

`research_seen_through`와 V3 봉인 레지스트리는 V3.1과 동일하게 계승됩니다.
