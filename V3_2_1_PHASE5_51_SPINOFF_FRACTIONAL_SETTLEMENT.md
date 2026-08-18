# V3.2.1 Phase 5.51 — Spin-off Fractional Settlement

## Outcome

The official Samsung Biologics spin-off decision explicitly states that less
than one Samsung Epis Holdings share is converted to cash using the new
company's first relisting-day close. The new company acquires the fractional
shares as treasury stock.

The implementation extracts this rule and produces reproducible settlement
examples for holdings of 1, 10, and 100 pre-event parent shares using the
verified 2025-11-24 close.

## Current boundary

The distributed-security fractional leg is now evidence-backed. Canonical total
return remains blocked because an equally explicit settlement rule for the
surviving-company fractional leg has not yet been identified and portfolio-level
position transfer is not implemented.

Outputs:

- `data/raw/v321/events/spinoff_fractional_rule_phase551_v321.csv`
- `data/raw/v321/events/spinoff_fractional_scenarios_phase551_v321.csv`
