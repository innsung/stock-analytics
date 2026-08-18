# V3.2.1 Phase 5.3 — Dividend / ETF Distribution / Corporate Action Acquisition

This phase does **not** change or retune the model.

## What it adds

- OpenDART annual dividend-disclosure acquisition (`alotMatter.json`).
- OpenDART disclosure-list scanning for candidate corporate-action reports.
- Annual retry/audit output.
- A reconciliation queue that explicitly leaves effective dates and factors blank until independently verified.
- No raw dividend disclosure is automatically promoted into a Total Return cash event.
- No corporate-action disclosure is automatically promoted into canonical `corporate_actions.csv`.

This preserves strict PIT semantics: a disclosed DPS amount is not the same thing as an ex-date/payment-date event.

## Command

```bat
python -m src.main acquire-payout-actions-v321 --universe-csv config\universe_kr_24.example.csv --start-year 2020 --end-year 2026 --output-dir data\raw\v321\events
```

Requires `DART_API_KEY` in `.env`.

Outputs:

- `data\raw\v321\events\dividend_disclosure_facts.csv`
- `data\raw\v321\events\corporate_action_disclosures.csv`
- `data\raw\v321\events\payout_action_acquisition_audit.csv`
- `data\raw\v321\events\payout_action_manifest.json`

Then:

```bat
python -m src.main build-event-reconciliation-v321 --dividend-facts-csv data\raw\v321\events\dividend_disclosure_facts.csv --action-disclosures-csv data\raw\v321\events\corporate_action_disclosures.csv --output-csv data\raw\v321\events\event_reconciliation_queue.csv
```

The reconciliation queue is **not** canonical corporate-action input. Phase 5.4 must resolve actual ex/effective dates and adjustment factors from a verified provider before `build-total-return-v321` can produce a VERIFIED Total Return history.

## Persistent-data safety

The distribution ZIP contains no `data/`, no database, no `.env`, and no `results/`.
Existing DB, raw KRX files, feature store, labels, checkpoints, backup DBs, and prior result bundles therefore remain local and untouched when source files are copied over the project.
