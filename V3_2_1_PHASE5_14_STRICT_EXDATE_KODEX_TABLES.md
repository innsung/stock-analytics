# V3.2.1 Phase 5.14 — Explicit Ex-date Strict Evidence + KODEX Table Parsing

This phase does not modify the model or the persistent database.

## 1. Promote explicit official EX_DATE rows only

```bat
python -m src.main build-explicit-stock-exdate-evidence-v321 --stock-dividend-date-resolution-csv data\raw\v321\events\stock_dividend_date_resolution_v321.csv --output-csv data\raw\v321\events\stock_dividend_explicit_exdate_strict_evidence_v321.csv --audit-csv data\raw\v321\events\stock_dividend_explicit_exdate_audit.csv
```

A row is strict only when:
- official date match is unique
- official date role is exactly `EX_DATE`
- `known_at <= EX_DATE <= 20260709`
- cash amount is positive
- official source exists

`RECORD_DATE` is intentionally not converted into an ex-date.

## 2. Export the preserved 069500 trading calendar

```bat
python -m src.main export-benchmark-calendar-v321 --benchmark-code 069500 --output-csv data\raw\v321\events\benchmark_069500_trading_calendar.csv
```

This reads the external persistent DB only; it does not modify it.

## 3. Build record-date calendar context

```bat
python -m src.main build-record-date-calendar-candidates-v321 --stock-dividend-date-resolution-csv data\raw\v321\events\stock_dividend_date_resolution_v321.csv --benchmark-prices-csv data\raw\v321\events\benchmark_069500_trading_calendar.csv --output-csv data\raw\v321\events\stock_dividend_record_date_calendar_candidates_v321.csv
```

The previous trading days are review context only. Settlement/holiday rules can make
a naive prior-trading-day conversion wrong, especially around year-end.

## 4. Parse saved KODEX high-signal bodies

```bat
python -m src.main parse-kodex-distribution-tables-v321 --bodies-dir data\raw\v321\events\kodex_069500\high_signal\bodies --output-csv data\raw\v321\events\kodex_069500\high_signal\kodex_distribution_table_candidates_v321.csv --audit-csv data\raw\v321\events\kodex_069500\high_signal\kodex_distribution_table_audit.csv
```

Only local contexts containing both a concrete date and positive won amount near
distribution/dividend wording are emitted. They remain candidates until the date role
(ex/record/pay) is verified.

## Safety
- research cutoff remains 2026-07-09
- explicit EX_DATE only for strict stock cash evidence
- record date is not silently mapped to ex-date
- KODEX date/amount pairs are candidates, not strict evidence
- release ZIP contains no `data/`, DB, `.env`, or `results/`
