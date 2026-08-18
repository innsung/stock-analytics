# V3.2.1 Phase 5.45 — Market Adjustment Verification

Three unique official candidates were checked against KRX adjusted and unadjusted
price series around their official event dates.

## Verified market factor

- Celltrion (`068270`)
- Legal action: bonus issue
- Official event date: 2026-06-05
- KRX adjustment effective date: 2026-06-04
- Adjustment factor: 1.0491345616973757
- Official known-at date: 2026-05-21

Samsung Biologics' spin-off and HD Hyundai's merger remain unresolved because raw
and adjusted price ratios alone are not safe evidence for those action types.

## Updated coverage

- New strict corporate-action evidence: 1
- Total merged strict evidence: 20
- Queue verified: 10 of 399
- Queue unresolved: 389
- Test suite: 160 passed

Date normalization was also corrected to accept official Korean date strings such
as `2026년 06월 05일` without weakening validation.
