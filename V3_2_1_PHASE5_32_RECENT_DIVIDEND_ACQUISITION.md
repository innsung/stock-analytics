# V3.2.1 Phase 5.32 — Recent Dividend Acquisition Manifest

The 21 Phase 5.31 P1 dividend gaps were cross-checked against recent OpenDART
decision disclosures and existing strict KIND evidence.

## Result

- Strict evidence already available: 3
- Ready for KIND market-notice search: 11
- Company disclosure discovery required first: 7
- Total P1 targets: 21

Existing strict coverage is available for SK Hynix (`000660`), Hyundai Motor
(`005380`), and Hyundai Mobis (`012330`). No missing row was promoted to verified.

## Command

```bat
python -m src.main build-recent-dividend-acquisition-manifest-v321
```

## Outputs

- `data/raw/v321/events/recent_dividend_acquisition_manifest_phase532_v321.csv`
- `data/raw/v321/events/recent_dividend_acquisition_summary_phase532_v321.json`
