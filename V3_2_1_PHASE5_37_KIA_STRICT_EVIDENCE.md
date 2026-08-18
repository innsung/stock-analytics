# V3.2.1 Phase 5.37 — Kia Strict Dividend Evidence

Kia's direct KIND cash-dividend decision was acquired and paired with the official
KIND market ex-date notice.

## Verified event

- Code: `000270`
- Common-share cash amount: KRW 6,800
- Record date: 2026-03-25
- Market ex-date: 2026-03-24
- Notice known-at date: 2026-03-23
- Strict validation errors: 0

Merged strict evidence now contains 12 events. The legacy annual queue row remains
unresolved because the new event falls outside the resolver's conservative 370-day
fallback window; that safety boundary was not relaxed.

## Outputs

- `data/raw/v321/events/kind_paired_market_strict_evidence_phase537_v321.csv`
- `data/raw/v321/events/official_event_evidence_strict_v321.csv`
- `data/raw/v321/events/event_verification_resolved_phase537_v321.csv`
