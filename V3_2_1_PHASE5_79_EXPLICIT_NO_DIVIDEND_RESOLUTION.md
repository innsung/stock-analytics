# V3.2.1 Phase 5.79 Explicit No-dividend Resolution

Rows with no direct dividend-decision filing are checked against the annual OpenDART dividend facts. A queue event becomes NOT_APPLICABLE only when both per-share cash dividend and total cash dividend are present as official fact types and every current-year value is explicitly empty (`-`) or zero.

This distinguishes a genuine no-dividend year from missing acquisition data. Official receipt numbers are retained in every evidence reference.

## Result

SK Biopharmaceuticals, EcoPro BM, Samsung Heavy Industries, and Samsung Biologics each had explicit empty current-year per-share and total cash-dividend facts. All four queue events were integrated as NOT_APPLICABLE.

Queue totals after integration are VERIFIED 22, NOT_APPLICABLE 41, and UNRESOLVED 336. The focused recent-dividend batch is 15 of 17 terminal, leaving only the two genuinely post-ex-date decisions for Samsung Electronics and Samsung SDI.

## Overall progress estimate

- Core application and research pipeline: approximately 90%.
- V3.2.1 PIT, risk, fail-closed, and regression safeguards: approximately 95%.
- Focused recent-dividend evidence batch: 15/17, approximately 88%.
- Full historical verification queue: 63/399 terminal, approximately 16%.
- Practical project completion, weighting working software more heavily than long-tail historical evidence: approximately 82%.
