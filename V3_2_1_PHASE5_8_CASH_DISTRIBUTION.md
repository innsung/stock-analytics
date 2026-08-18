# V3.2.1 Phase 5.8 — Official Cash Dividend / ETF Distribution Evidence

This phase does not change the model and does not mutate the persistent database.

## Purpose

Cash distributions need an actual official ex/effective date and cash amount.
OpenDART annual dividend disclosures can support the amount, but they do not by
themselves establish the Total Return event date. ETF 069500 distributions are
handled separately from corporate OpenDART dividends.

## 1. Build stock cash-amount candidates from OpenDART facts

```bat
python -m src.main build-stock-cash-amount-candidates-v321 --dividend-facts-csv data\raw\v321\events\dividend_disclosure_facts.csv --verification-csv data\raw\v321\events\event_verification_v321.csv --output-csv data\raw\v321\events\stock_cash_amount_candidates_v321.csv --audit-csv data\raw\v321\events\stock_cash_amount_candidates_audit.csv
```

The output supplies only DART amount candidates. `effective_date` remains blank.

## 2. Create the official cash-event sheet

```bat
python -m src.main prepare-official-cash-events-v321 --verification-csv data\raw\v321\events\event_verification_v321.csv --output-csv data\raw\v321\events\official_cash_events_v321.csv
```

Rows for 069500 are explicitly marked `ETF_DISTRIBUTION`; stock rows are
`CASH_DIVIDEND`.

The template must be populated from official ex/effective-date evidence before
strict validation.

## 3. Strict validation after actual official events are populated

```bat
python -m src.main validate-official-cash-events-v321 --official-cash-events-csv data\raw\v321\events\official_cash_events_v321.csv --output-csv data\raw\v321\events\cash_distribution_strict_evidence_v321.csv --audit-csv data\raw\v321\events\cash_distribution_strict_evidence_audit.csv
```

Strict rules:
- queue_event_id required
- effective/ex-date <= 2026-07-09
- known_at <= effective date
- cash amount > 0
- adjustment factor exactly 1
- non-placeholder official source/reference
- ETF_DISTRIBUTION reserved for 069500 in the current research universe

## 4. Cross-check stock cash amounts against OpenDART amount candidates

```bat
python -m src.main compare-cash-amount-candidates-v321 --strict-cash-evidence-csv data\raw\v321\events\cash_distribution_strict_evidence_v321.csv --amount-candidates-csv data\raw\v321\events\stock_cash_amount_candidates_v321.csv --output-csv data\raw\v321\events\cash_amount_crosscheck_audit.csv
```

A DART mismatch is surfaced as an audit issue rather than silently changing the
official cash event.

## Safety

- No price-gap inference of dividends.
- No automatic year-end ex-date assumptions.
- No conversion of annual DPS disclosure date into an effective date.
- Release ZIP contains no `data/`, DB, `.env`, or `results/`.
