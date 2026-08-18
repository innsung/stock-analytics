# V3.2.1 Phase 5.12 — KODEX Endpoint Probe + Stock Dividend Decision Resolver

No model change and no persistent DB mutation.

## 1. Rank and safely probe KODEX endpoint candidates

Phase 5.11 discovered 350 same-origin URL/API candidates. Phase 5.12 ranks them and
GET-probes only the top candidates on `m.samsungfund.com`.

```bat
python -m src.main rank-probe-kodex-endpoints-v321 --candidate-csv data\raw\v321\events\kodex_069500\dynamic\kodex_dynamic_endpoint_candidates_v321.csv --output-csv data\raw\v321\events\kodex_069500\dynamic\kodex_endpoint_probe_v321.csv --top-n 25
```

Probe results remain discovery metadata, never cash-event evidence.

## 2. Acquire official dividend-decision disclosures

OpenDART's periodic `alotMatter` API provides dividend facts but not an ex-date. This
phase additionally searches the official disclosure list for dividend-decision /
dividend-record-date reports.

```bat
python -m src.main acquire-stock-dividend-decisions-v321 --universe-csv config\universe_kr_24.example.csv --start 20200101 --end 20260709 --output-csv data\raw\v321\events\stock_dividend_decision_disclosures_v321.csv --audit-csv data\raw\v321\events\stock_dividend_decision_disclosures_audit.csv
```

The receipt date is `known_at` evidence, not the ex-date.

## 3. Combine 111 refined amount candidates with decision disclosures

```bat
python -m src.main build-stock-dividend-exdate-queue-v321 --refined-amount-candidates-csv data\raw\v321\events\stock_cash_amount_candidates_refined_v321.csv --dividend-decisions-csv data\raw\v321\events\stock_dividend_decision_disclosures_v321.csv --output-csv data\raw\v321\events\stock_dividend_exdate_resolution_queue_v321.csv
```

The output deliberately leaves `effective_date` blank. A separate official ex-date or
record-date-to-ex-date source is still required for strict Total Return evidence.

## Safety

- research cutoff remains 2026-07-09
- no endpoint probe is treated as event evidence
- DART receipt date is not treated as ex-date
- ambiguous decision matches remain unresolved
- release ZIP contains no `data/`, DB, `.env`, or `results/`
