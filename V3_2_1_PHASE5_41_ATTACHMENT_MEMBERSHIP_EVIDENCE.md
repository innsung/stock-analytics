# V3.2.1 Phase 5.41 — Aggregate Attachment Membership Evidence

The KOSPI aggregate notice abbreviates its body with "LG Chem and others". Its
official attached PDF contains the complete 127-company/157-security membership
table. The attachment was extracted and visually checked before use.

## Verified events

- Amorepacific (`090430`): KRW 1,240, record date 2026-03-31,
  ex-date 2026-03-30
- LG Household & Health Care (`051900`): KRW 1,000, record date 2026-03-31,
  ex-date 2026-03-30

The validator now preserves an official membership-attachment reference when a
company is named in the official attachment rather than the abbreviated notice
body. An attachment reference is required for this path.

## Result

- New strict evidence rows: 2
- Total merged strict evidence rows: 19
- Invalid rows: 0
- Test suite: 156 passed
