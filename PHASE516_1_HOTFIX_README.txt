V3.2.1 Phase 5.16.1 Hotfix

Purpose:
- Ensure Phase 5.16 CLI commands are actually registered in src/main.py.
- Add phase516-selfcheck command.
- No data/, results/, DB, or .env files are included.

Apply:
1) Extract this ZIP directly into C:\dev\stock-analytics
2) Choose overwrite/replace for existing source files.
3) Do NOT delete the existing data folder. This ZIP contains no data folder.

Verify:
python -m src.main phase516-selfcheck

Expected:
[V3.2.1 Phase 5.16.1 Self-check]
crosscheck-kind-dividends-v321: REGISTERED
discover-kodex-next-hops-v321: REGISTERED
phase516 module: IMPORT_OK
상태: PHASE516_APPLIED
