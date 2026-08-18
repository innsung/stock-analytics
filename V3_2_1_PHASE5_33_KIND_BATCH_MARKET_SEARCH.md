# V3.2.1 Phase 5.33 — KIND Batch Market-Notice Search

The 11 Phase 5.32 search-ready companies were queried against monthly KIND market
action result windows from January through July 9, 2026.

## Result

- Target companies: 11
- Common-share official notices discovered: 5
- Companies represented: 4
- Shinhan Financial Group: 2 notices
- HD Hyundai, Hana Financial Group, KB Financial Group: 1 notice each

These are discovery candidates only. They are not strict cash-dividend evidence
until the official dividend amount and record date are paired and validated.

## Command

```bat
python -m src.main discover-kind-market-notices-batch-v321
```

## Outputs

- `data/raw/v321/events/kind_batch_market_notices_phase533_v321.csv`
- `data/raw/v321/events/kind_batch_market_search_audit_phase533_v321.csv`
