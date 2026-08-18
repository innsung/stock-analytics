# V3.2.1 Phase 5.54 — Guarded Total Return Entrypoint

## Outcome

The canonical total-return builder now requires explicit proof that the complex
corporate-action coverage gate passed. Legacy or manually constructed coverage
files that omit `complex_actions_complete` or `coverage_gate_status` are rejected.

The command-line entrypoint defaults to the Phase 5.53 guarded coverage file and
the canonical corporate-action file. With the current evidence, execution stops
cleanly because the complex-action gate is blocked; it cannot silently fall back
to the older unguarded coverage declaration.

## Required gate fields

- `complex_actions_complete: true`
- `coverage_gate_status: PASS`
- `cash_distributions_complete: true`
- `capital_actions_complete: true`

All four conditions must hold before a derived canonical total-return series can
be generated.
