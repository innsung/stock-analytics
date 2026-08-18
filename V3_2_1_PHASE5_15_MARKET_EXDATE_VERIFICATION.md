# V3.2.1 Phase 5.15 — Market Ex-date Verification Queue

This phase does not change the model and does not mutate the persistent DB.

Phase 5.14 produced:
- 111 stock cash-dividend amount/date-resolution rows
- 47 unique `RECORD_DATE` candidates
- 0 explicit `EX_DATE` strict rows
- 0 KODEX date+amount table pairs

Phase 5.15 therefore does not guess harder. It creates a source-backed market
verification interface.

## 1. Build prioritized official market ex-date queue

```bat
python -m src.main build-market-exdate-verification-queue-v321 --stock-dividend-date-resolution-csv data\raw\v321\events\stock_dividend_date_resolution_v321.csv --record-date-calendar-candidates-csv data\raw\v321\events\stock_dividend_record_date_calendar_candidates_v321.csv --output-csv data\raw\v321\events\stock_dividend_market_exdate_verification_queue_v321.csv
```

Rows with a unique official `RECORD_DATE` receive highest priority. Nearby benchmark
trading days are supplied only as context. `market_ex_date` remains blank.

## 2. Validate only actual official market ex-date observations

After an official KRX/issuer/source row has been supplied:

```bat
python -m src.main validate-official-market-exdates-v321 --verification-csv data\raw\v321\events\stock_dividend_market_exdate_verification_queue_v321.csv --strict-evidence-csv data\raw\v321\events\stock_dividend_market_exdate_strict_evidence_v321.csv --audit-csv data\raw\v321\events\stock_dividend_market_exdate_strict_audit.csv
```

Strict evidence requires:
- populated market ex-date
- positive cash amount
- PIT-valid known_at
- non-placeholder official source/reference
- ex-date <= 2026-07-09

No calendar suggestion is used as strict evidence.

## 3. Summarize KODEX high-signal responses

```bat
python -m src.main summarize-kodex-high-signal-bodies-v321 --response-audit-csv data\raw\v321\events\kodex_069500\high_signal\kodex_high_signal_response_audit.csv --field-candidates-csv data\raw\v321\events\kodex_069500\high_signal\kodex_high_signal_field_candidates.csv --output-json data\raw\v321\events\kodex_069500\high_signal\kodex_high_signal_summary_v321.json
```

This makes the current KODEX blocker explicit: high-signal responses were reachable,
but no structured date/amount distribution schema has yet been identified.

## Safety
- research cutoff remains 2026-07-09
- no record-date-to-ex-date assumption is promoted
- no blank source can become strict evidence
- release ZIP contains no `data/`, DB, `.env`, or `results/`
