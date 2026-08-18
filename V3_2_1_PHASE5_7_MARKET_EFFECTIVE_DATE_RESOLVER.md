# V3.2.1 Phase 5.7 — KRX Market Effective-Date / Adjustment-Factor Resolver

No model or persistent-DB mutation is introduced.

This phase compares KRX adjusted and unadjusted OHLCV around detailed OpenDART
corporate-action candidates. A unique adjusted/raw ratio breakpoint near an official
candidate can produce strict market evidence for safe factor actions:

- BONUS
- SPLIT
- REVERSE_SPLIT

The factor is derived from the change in `adjusted_close / raw_close` across the
market breakpoint. The OpenDART disclosure provides legal/event context and `known_at`;
KRX price-series behavior provides the market adjustment boundary.

## Deliberate exclusions

MERGER, SPINOFF, RIGHTS, cash dividends, and ETF distributions are not automatically
verified from price gaps. Their economic treatment can be more complex or requires an
actual cash amount/ex-date source.

## Command

```bat
python -m src.main build-market-adjustment-evidence-v321 --official-candidates-csv data\raw\v321\events\official_candidates\official_event_candidates_v321.csv --output-csv data\raw\v321\events\market_adjustment_evidence_v321.csv --audit-csv data\raw\v321\events\market_adjustment_evidence_audit.csv
```

If other strict evidence files later exist, merge them with:

```bat
python -m src.main merge-strict-evidence-v321 --evidence-csv data\raw\v321\events\market_adjustment_evidence_v321.csv --evidence-csv <other_strict_evidence.csv> --output-csv data\raw\v321\events\official_event_evidence_strict_v321.csv
```

Then pass the merged strict evidence to `resolve-official-events-v321`.

## Safety

- Research cutoff remains 2026-07-09.
- A price discontinuity alone never determines legal action type.
- Cash distributions are never inferred from price gaps.
- Ambiguous/missing breakpoints remain UNRESOLVED.
- Release ZIP contains no `data/`, DB, `.env`, or `results/`.
