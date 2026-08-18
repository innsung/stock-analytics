# V3.2.1 Phase 5.82 Historical Backlog Execution Router

Phase 5.82 converts the remaining historical backlog into evidence-specific execution lanes without changing any resolution status.

The router separates periodic-report dividend facts from corporate-action documents, distinguishes primary decisions from amendments, attachments, results, and market-administration notices, and assigns candidate cluster keys for subsequent legal-event linkage. A route is operational metadata only; it is never strict evidence and cannot enter total-return calculation.

The next phase must start with `DIVIDEND_DECISION_EXDATE_LINKAGE`, then process corporate-action legal-event chains before reviewing primary adjustment mechanics or proving non-applicability.
