# V3.2.1 Phase 5.4 — Effective Date / Ex-Date / Adjustment Factor Verification

This phase does not modify or retune the model.

## Goal

Convert the 399-row Phase 5.3 reconciliation queue into a traceable verification workflow.
Only rows supported by a real effective/ex-date, a `known_at` date, an action type,
an adjustment factor/cash amount, and a non-placeholder verification source may be
promoted to canonical corporate actions.

## Step 1 — Prepare the verification sheet

```bat
python -m src.main prepare-event-verification-v321 --queue-csv data\raw\v321\events\event_reconciliation_queue.csv --output-csv data\raw\v321\events\event_verification_v321.csv
```

Outputs:
- `event_verification_v321.csv`
- `event_verification_v321_queue_registry.csv`

Each original queue row receives a stable `queue_event_id`.

`resolution_status` accepts:
- `VERIFIED`
- `NOT_APPLICABLE`
- `UNRESOLVED`

A single queue event may be duplicated into multiple `VERIFIED` rows when one annual
dividend disclosure represents multiple actual cash events.

## Step 2 — Finalize only after evidence has been reconciled

```bat
python -m src.main finalize-event-reconciliation-v321 --verification-csv data\raw\v321\events\event_verification_v321.csv --queue-registry-csv data\raw\v321\events\event_verification_v321_queue_registry.csv --canonical-output-csv data\v321_foundation\corporate_actions_v321.csv --audit-output-csv data\v321_foundation\event_reconciliation_audit.csv --coverage-json data\v321_foundation\total_return_coverage_v321.json --coverage-start 20200101 --coverage-end 20260709
```

Coverage is complete only when every original queue event has a terminal resolution
(`VERIFIED` or `NOT_APPLICABLE`). Any `UNRESOLVED` queue event keeps Total Return blocked.

## Strict VERIFIED rules

- effective date is valid and <= 2026-07-09
- known_at is valid and <= effective date
- verification source is non-empty and non-placeholder
- action type is supported
- adjustment factor > 0
- cash amount >= 0
- dividend/distribution rows require factor=1 and cash amount > 0
- non-cash capital actions require cash amount=0

## Persistent data safety

The release archive contains no `data/`, no DB, no `.env`, and no `results/`.
The persistent DB may remain outside the project, e.g.
`C:\stock-analytics-data\stock_analytics.db`.
