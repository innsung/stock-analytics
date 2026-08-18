# V3.2.1 Phase 5.53 — Complex Action Coverage Gate

## Outcome

A fail-closed coverage gate now connects complex corporate-action evidence to
the total-return coverage declaration. Any required evidence item whose status
is not `VERIFIED` forces both `capital_actions_complete` and `complete` to
`false`, even if an upstream coverage file incorrectly declares them true.

For the current Samsung Biologics spin-off, the missing surviving-leg
fractional rule creates one blocker. The guarded coverage therefore remains
ineligible for canonical total-return generation.

Outputs:

- `data/v321_foundation/total_return_coverage_guarded_phase553_v321.json`
- `data/raw/v321/events/complex_action_coverage_gate_phase553_v321.csv`
