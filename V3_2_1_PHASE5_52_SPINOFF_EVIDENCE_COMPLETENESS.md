# V3.2.1 Phase 5.52 — Spin-off Evidence Completeness

## Outcome

The full OpenDART filing for receipt `20250822000109` was downloaded and checked
alongside the structured major-event response. Four required facts are verified:

- capital-reduction ratio;
- new-company allocation ratio;
- new-company fractional-share cash settlement;
- first joint trading date.

The filing does not separately state how a fractional surviving-company leg is
settled. This absence is now recorded as a required missing item rather than
filled by assumption.

## Decision

The event remains unsuitable for canonical portfolio position transfer. The
parent adjusted-price factor remains usable only for parent price-series
continuity, while the distributed-security ledger remains an audit artifact.

Outputs:

- `data/raw/v321/events/spinoff_evidence_completeness_phase552_v321.csv`
- `data/raw/v321/events/corporate_action_documents_phase552/20250822000109.xml`
