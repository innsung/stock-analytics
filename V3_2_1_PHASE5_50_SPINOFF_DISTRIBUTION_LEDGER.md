# V3.2.1 Phase 5.50 — Spin-off Distribution Ledger

## Outcome

The verified Samsung Biologics human spin-off is represented as a balanced,
two-leg position distribution per pre-event parent share:

- 0.6503913 Samsung Biologics (`207940`) surviving shares
- 0.3496087 Samsung Epis Holdings (`0126Z0`) distributed shares

Both legs are valued on the first joint trading date, 2025-11-24. The ledger
preserves the distributed security instead of treating it as cash or hiding it
inside a parent-only adjustment factor.

## Safety boundary

The output is marked `VALUED_NOT_CANONICAL_TOTAL_RETURN`. Fractional-share cash
settlement, portfolio position transfer, and subsequent child-security returns
must be implemented and verified before this event can feed the canonical total
return history.

Output: `data/raw/v321/events/spinoff_distribution_ledger_phase550_v321.csv`
