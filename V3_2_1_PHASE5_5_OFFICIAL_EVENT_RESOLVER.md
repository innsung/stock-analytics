# V3.2.1 Phase 5.5 — Official Event Resolver

This phase does not modify or retune the model and does not alter the persistent DB.

## Purpose

Resolve the Phase 5.4 verification queue from strict official-event evidence.

Resolution rules:
- `VERIFIED`: only when a strict official evidence row matches.
- `NOT_APPLICABLE`: only with an explicit source-backed not-applicable evidence row.
- `UNRESOLVED`: missing or ambiguous evidence remains unresolved.
- No heuristic can silently promote a row.

A single annual dividend queue item may expand into multiple verified cash events
(interim/final distributions) when the evidence explicitly contains multiple events.

## 1. Create official evidence template

```bat
python -m src.main prepare-official-event-evidence-v321 --verification-csv data\raw\v321\events\event_verification_v321.csv --output-csv data\raw\v321\events\official_event_evidence_v321.csv
```

Required evidence fields:
- queue_event_id
- code
- event_family
- source_reference_date
- effective_date
- known_at
- action_type
- adjustment_factor
- cash_amount
- verification_source
- verification_reference

The blank template is not valid evidence. Actual official-source observations must
be inserted before resolution.

## 2. Resolve evidence

```bat
python -m src.main resolve-official-events-v321 --verification-csv data\raw\v321\events\event_verification_v321.csv --evidence-csv data\raw\v321\events\official_event_evidence_v321.csv --output-csv data\raw\v321\events\event_verification_resolved_v321.csv --audit-csv data\raw\v321\events\official_event_resolution_audit.csv
```

Optional explicit NOT_APPLICABLE evidence:

```bat
--not-applicable-csv data\raw\v321\events\not_applicable_evidence_v321.csv
```

Schema:
- queue_event_id
- verification_source
- verification_reference
- resolution_note

## 3. Finalize only when unresolved count is zero

Use the Phase 5.4 `finalize-event-reconciliation-v321` command with
`event_verification_resolved_v321.csv`.

## Safety

The release ZIP contains no `data/`, DB, `.env`, or `results/`.
The persistent DB at `C:\stock-analytics-data\stock_analytics.db` is not touched.

A new smoke test imports `src.main` and checks that all Phase 5.3, 5.4, and 5.5
functions are truly available in the CLI namespace.
