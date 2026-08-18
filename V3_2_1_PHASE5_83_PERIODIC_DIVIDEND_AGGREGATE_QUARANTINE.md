# V3.2.1 Phase 5.83 Periodic Dividend Aggregate Quarantine

The 120 historical `OpenDART alotMatter` queue rows are annual periodic-report aggregates, not discrete cash-dividend events. In 119 rows the queue reference date precedes the actual annual-report receipt date; the remaining row matches it. None may be treated as a point-in-time dividend event date.

Phase 5.83 validates each placeholder against its raw OpenDART payload, quarantines only uniquely matched annual aggregates as `NOT_APPLICABLE`, and emits a one-for-one replacement requirement. The replacement queue keeps the underlying coverage obligation open: every actual dividend still requires a direct dividend decision and an official market ex-date before total-return inclusion.
