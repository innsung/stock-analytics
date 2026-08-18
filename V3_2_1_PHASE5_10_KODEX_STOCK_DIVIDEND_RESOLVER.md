# V3.2.1 Phase 5.10 — KODEX Historical Distribution Acquisition + Stock Dividend Resolution

This phase does not change the model and does not mutate the persistent DB.

## KODEX 200 acquisition

The official Samsung Asset Management product page is fetched directly. The parser
does **not** fabricate events from the stated quarterly distribution policy. It only
emits candidates when the page contains a concrete calendar date near an explicit
cash distribution amount.

```bat
python -m src.main acquire-kodex-distributions-v321 --output-dir data\raw\v321\events\kodex_069500
```

Outputs include the raw official HTML, parsed candidate CSV, and manifest.

Candidates are not strict evidence until the role of the date (ex/record/pay) and a
pre-event `announced_at` are verified.

## Stock dividend ambiguity report

```bat
python -m src.main build-stock-dividend-ambiguity-report-v321 --amount-audit-csv data\raw\v321\events\stock_cash_amount_candidates_audit.csv --amount-candidates-csv data\raw\v321\events\stock_cash_amount_candidates_v321.csv --output-csv data\raw\v321\events\stock_dividend_ambiguity_report_v321.csv
```

The report turns the existing 37 unique / 74 ambiguous / 33 missing split into an
explicit resolution queue. No missing amount is converted to zero.

## Safety

- research cutoff remains 2026-07-09
- policy dates are not historical events
- price gaps are not cash dividends
- ZIP contains no data/, DB, .env, or results/
