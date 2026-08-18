# V3.2.1 Data Integrity Phase 2

이 단계는 새 모델을 추가하지 않는다. V3.1 Champion과 V3.2.1 공통 위험관리·검증 의미를 유지하면서, 데이터 증거와 종목 고착 원인을 강화한다.

## 1. Historical valuation snapshots

`config/valuation_snapshots_v321.template.csv` 형식으로 실제 과거 관측값을 준비한다.

필수 열:

- `code`
- `snapshot_date`: 실제 시장 관측일
- `price`, `market_cap`
- `per`, `pbr`, `eps`, `bps`, `dividend_yield`
- `known_at`: 당시 시스템에서 알 수 있었던 날짜. 반드시 `known_at <= snapshot_date`.
- `source`: 검증 가능한 출처 식별자

2026-07-10 이후 snapshot은 V3.2.1 연구 입력으로 허용하지 않는다.

검증 및 DB 반영:

```bash
python -m src.main import-valuation-snapshots-v321 --csv config/valuation_snapshots_v321.csv
```

그 다음 기존 `build-feature-store`를 다시 실행한다. 그래야 `valuation_snapshot_date`, `valuation_per`, `valuation_pbr`가 feature store에 point-in-time 방식으로 들어간다.

## 2. Total return / corporate actions / historical universe

기존 템플릿을 채워 `ml-diagnose-v321`에 전달한다.

- `config/total_return_history.template.csv`
- `config/corporate_actions.template.csv`
- `config/universe_history_v3.template.csv`

데이터가 없으면 감사 결과를 억지로 통과시키지 않는다. `*_INPUT_NOT_AVAILABLE`, `OBSERVED_DATA_ONLY`, `FINANCIAL_DISCLOSURE_PIT_PARTIAL` 상태를 유지한다.

## 3. Selection Persistence Audit

V3.2.1 결과에 다음 파일이 추가된다.

`<output-prefix>_selection_persistence_audit.csv`

종목별로 다음을 분리한다.

- 선택 기간 수 / 전체 기간 수 / 보유율
- 최대 연속 선택 횟수
- 평균 모델 score와 선택 집합 내 score percentile
- 실제 향후 수익률
- 동일가중 universe 대비 초과수익
- ETF 대비 초과수익
- 지속 선택 여부(`persistent_flag`, 80% 이상)
- 지속 선택이 실제 성과로 뒷받침되는지(`persistent_but_supported`)

기존 `validation_individual_stock_not_fixed` 기준은 그대로 둔다. 대신 `persistent_stock_selection_economically_supported`를 추가해 “고착”과 “계속 상위권이어서 합리적으로 재선택된 경우”를 별도로 보여준다.

## 4. Sealed-test rule

- `research_seen_through = 20260709` 고정
- 2026-07-10 이후 데이터로 feature, threshold, candidate, risk rule 재튜닝 금지
- daily shadow는 계속 허용
- live order는 계속 차단
- 미래 sealed test는 기존 계획대로 충분한 비중첩 20거래일 forward-return 평가점이 쌓인 뒤 실시
