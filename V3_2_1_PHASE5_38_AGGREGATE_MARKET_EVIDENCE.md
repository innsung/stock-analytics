# V3.2.1 Phase 5.38 — Aggregate Market Notice Evidence

Official KRX/KIND aggregate ex-dividend notices were checked for search targets
that had no individual company notice.

## Verified events

- LG Chem (`051910`): KRW 2,000, record date 2026-03-31, ex-date 2026-03-30
- EcoPro BM (`247540`): KRW 100, record date 2026-03-31, ex-date 2026-03-30

Both decision documents and aggregate market notices were acquired from KIND and
validated without errors.

## Result

- Aggregate notice sources checked: 3
- Target companies matched: 2
- New strict evidence rows: 2
- Total merged strict evidence rows: 14
- Test suite: 155 passed

The legacy annual queue remains fail-closed because these 2026 events are outside
its conservative automatic fallback window.
