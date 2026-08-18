# V3.2.1 Phase 5.36 — Company Recovery and Search Refresh

The priority queue was rebuilt after Phase 5.35, then missing company names were
recovered from original OpenDART fact payloads.

## Result

- Remaining unresolved events: 395
- Remaining recent-dividend gaps: 20
- Strict-covered recent-dividend codes: 6
- Missing company names recovered: 7 of 7
- Remaining search targets: 14
- Additional official market notice found: Kia (`000270`)

KIND company search also identified Kia's direct cash-dividend decision receipt
`20260128000342`. It remains unpromoted until its original decision document is
downloaded, parsed, and paired with the market notice.

## Outputs

- `data/raw/v321/events/event_resolution_priority_queue_phase536_v321.csv`
- `data/raw/v321/events/recent_dividend_acquisition_enriched_phase536_v321.csv`
- `data/raw/v321/events/company_name_recovery_audit_phase536_v321.csv`
- `data/raw/v321/events/kind_batch_market_notices_phase536_v321.csv`
