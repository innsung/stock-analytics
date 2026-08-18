# V3.2.1 Phase 5.47 — Corporate Action Document Parser

The six acquired original filings were parsed for shareholder allotment dates,
new-share listing dates, capital-reduction dates, and ratios.

## Result

- Parsed documents: 6
- Events after the research cutoff: 3
- Filing known-at date after the extracted event date: 2
- Minor capital reduction requiring semantic review: 1
- Immediately eligible for KRX automatic adjustment verification: 0

Notable extracted fields include EcoPro BM's 2026-09-04 allotment date, SK Hynix's
2026-07-29 planned listing date, Samsung SDI's 2025-04-11 allotment date and
0.1414150945 ratio, and LG Household & Health Care's 2026-04-27 capital-reduction
date with a 0.07% reduction.

No row was promoted because each fails at least one PIT, cutoff, or semantic safety
condition.

## Integrity

- Test suite: 162 passed
