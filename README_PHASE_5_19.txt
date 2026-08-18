V3.2.1 Phase 5.18 hotfix + Phase 5.19
======================================

Included changes
----------------
1. Fix the Phase 5.18 acptNo/docNo regular expressions.
2. Persist kind_acpt_no and kind_doc_no in Phase 5.16 output and audit CSVs.
3. Extract docNo from the selected KIND mainDoc option, with a safe fallback.
4. Add regression tests for KIND document ID extraction.

Apply
-----
Extract this archive into the C:\dev\stock-analytics repository root and merge
the src and tests directories.

Verify
------
python -m pytest -q

Expected result in the source workspace used to build this package:
135 passed

Operational note
----------------
The Phase 5.18 dry-run found 47 of 47 rows as KIND_ID_UNAVAILABLE. A subsequent
Phase 5.19 live check persisted all 47 acptNo values, but KIND returned no docNo
values at that time. Re-run Phase 5.16 when KIND is serving normal viewer data,
then run the Phase 5.18 dry-run/retry flow again.
