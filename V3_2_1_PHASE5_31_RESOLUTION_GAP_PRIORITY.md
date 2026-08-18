# V3.2.1 Phase 5.31 — Resolution Gap Priority Queue

The unresolved Phase 5.30 verification rows are now separated into deterministic,
fail-closed work queues.

## Counts

- P1 recent dividends (2025+): 21
- P2 recent corporate actions (2025+): 48
- P3 historical dividends: 120
- P4 historical corporate actions: 207
- Total unresolved: 396

The next acquisition target is the 21 P1 recent-dividend rows. No unresolved row
was promoted or assigned an inferred effective date during prioritization.

## Command

```bat
python -m src.main prioritize-resolution-gaps-v321
```

## Outputs

- `data/raw/v321/events/event_resolution_priority_queue_phase531_v321.csv`
- `data/raw/v321/events/event_resolution_priority_summary_phase531_v321.json`
