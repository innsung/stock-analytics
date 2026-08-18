# V3.2.1 Phase 5.78 Pre-ex-date Provenance Recovery

Late-decision dividend rows are audited at filing-lineage level. Identical corrected terms retain the latest canonical document while `known_at` is recovered from the earliest identical official filing.

This distinguishes genuinely post-ex-date decisions from a later corrective copy. Recovered events still require an explicit official KIND application date before strict promotion.

## Result

- Hyundai Mobis: earliest identical filing 2025-01-23, latest corrective filing 2025-03-24, KRW 5,000, official KIND ex-date 2025-03-21. Strictly verified and integrated.
- Samsung Electronics: KRW 363 decision first published 2025-01-31 after the 2024-12-30 calendar search point. No pre-ex-date amount disclosure found.
- Samsung SDI: KRW 1,000 decision first published 2025-01-24 after the 2024-12-30 calendar search point. No pre-ex-date amount disclosure found.
- Queue totals after integration: VERIFIED 22, NOT_APPLICABLE 37, UNRESOLVED 340.
- Remaining recent-dividend targets: 6.

## Project progress interpretation

The software pipeline and V3.2.1 safety controls are implemented and regression-tested. Remaining work is dominated by historical evidence completion rather than missing application code. Of 399 verification queue events, 59 are terminal (22 verified and 37 not applicable) and 340 remain unresolved. In the focused recent-dividend batch, 11 of the original 17 targets are now resolved and 6 remain.
