# V3.2.1 Historical Data Acquisition — Phase 4

## 목적
새 모델/재튜닝 없이 V3.2.1의 PIT 데이터 기반을 실제 과거 관측 데이터로 채우는 수집 계층이다.
연구 경계는 `20260709`로 고정한다.

## 신규 CLI
```bat
python -m pip install -r requirements.txt

python -m src.main acquire-historical-data-v321 ^
  --universe-csv config\universe_kr_24.example.csv ^
  --start 20200101 ^
  --end 20260709 ^
  --frequency m ^
  --output-dir data\raw\v321
```

KRX 지수 구성종목 관측도 함께 시도하려면 `--index-code`를 추가한다. 예: KOSPI200 지수 코드는 사용하는 데이터 공급자 정의에 맞춰 확인 후 입력한다.

## 생성물
- `valuation_snapshots.csv`: code/date별 종가, 시가총액, PER/PBR/EPS/BPS/DIV, known_at, source
- `valuation_acquisition_audit.csv`: 종목별 성공/실패/행수
- `universe_observations.csv`: `--index-code` 사용 시 관측된 구성종목 스냅샷
- `universe_acquisition_audit.csv`
- `acquisition_manifest.json`

## 엄격 규칙
- `20260710` 이후 데이터 수집을 V3.2.1 연구 입력으로 허용하지 않는다.
- source는 `KRX_PYKRX_EOD`로 명시한다.
- valuation의 `known_at`은 EOD observation date를 보존한다.
- 현재 valuation을 과거 날짜에 복사하지 않는다.
- 보간/역채움하지 않는다.
- adjusted OHLCV를 dividend-inclusive total return으로 간주하지 않는다.
- corporate action은 공시일과 실제 효력일 매핑 전에는 canonical 데이터로 승격하지 않는다.
- index/universe snapshot 관측치를 연속 membership interval로 임의 변환하지 않는다.

## 다음 단계
1. valuation 수집 후 `import-valuation-snapshots-v321` 실행
2. feature store 재생성
3. OpenDART/공식 원자료 기반 corporate-action effective-date reconciliation 추가
4. 배당/ETF 분배금 포함 total-return ledger 구축
5. historical universe/index membership의 공식 효력일 기반 canonicalization
