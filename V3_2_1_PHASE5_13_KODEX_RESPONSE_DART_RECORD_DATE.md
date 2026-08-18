# V3.2.1 Phase 5.13 — KODEX Response Parser + DART Dividend Record-Date Extraction

This phase does not change the model and does not mutate the persistent DB.

## KODEX high-signal response inspection

Phase 5.12 found 10 high-response-score endpoint candidates. Phase 5.13 re-fetches
only those high-signal endpoints, saves their response bodies for audit, and inspects
JSON/HTML for date-like and amount-like fields.

```bat
python -m src.main inspect-kodex-high-signal-responses-v321 --probe-csv data\raw\v321\events\kodex_069500\dynamic\kodex_endpoint_probe_v321.csv --output-dir data\raw\v321\events\kodex_069500\high_signal
```

Outputs:
- saved response bodies
- `kodex_high_signal_response_audit.csv`
- `kodex_high_signal_field_candidates.csv`
- manifest

A field candidate is still not historical ETF distribution evidence.

## DART original filing record-date extraction

The OpenDART `document.xml` API is used with each dividend-decision `rcept_no`.
The downloaded official filing archive is scanned for explicit labels such as
`배당기준일` or `배당락일`.

```bat
python -m src.main extract-dart-dividend-record-dates-v321 --decision-disclosures-csv data\raw\v321\events\stock_dividend_decision_disclosures_v321.csv --output-csv data\raw\v321\events\stock_dividend_official_date_candidates_v321.csv --audit-csv data\raw\v321\events\stock_dividend_official_date_candidates_audit.csv
```

Only a unique explicit label/date pair is emitted as a candidate. `known_at` remains
the DART receipt date.

## Merge with the 111 amount candidates

```bat
python -m src.main merge-dividend-date-candidates-v321 --exdate-queue-csv data\raw\v321\events\stock_dividend_exdate_resolution_queue_v321.csv --dart-record-candidates-csv data\raw\v321\events\stock_dividend_official_date_candidates_v321.csv --output-csv data\raw\v321\events\stock_dividend_date_resolution_v321.csv
```

If DART yields a `RECORD_DATE`, it remains a record date. It is not silently converted
to a prior trading-day ex-date. The next phase must map record dates using an official
KRX trading calendar and market convention.

## Safety
- research cutoff remains 2026-07-09
- response bodies and parsed fields are audit artifacts, not automatic evidence
- DART receipt date is never used as ex-date
- record date is never silently converted to ex-date
- release ZIP contains no `data/`, DB, `.env`, or `results/`
