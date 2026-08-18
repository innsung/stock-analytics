from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_final_promotion_gate_v321(
    *, payload_summary_json: str, restore_summary_json: str, audit_csv: str, summary_json: str
) -> dict:
    payload = json.loads(Path(payload_summary_json).read_text(encoding="utf-8"))
    restore = json.loads(Path(restore_summary_json).read_text(encoding="utf-8"))
    payload_path = Path(payload.get("payload_zip", ""))
    actual_hash = _sha256(payload_path) if payload_path.is_file() else ""
    checks = [
        ("RELEASE_ID_CONSISTENT", payload.get("release_id") == restore.get("release_id") == "V3.2.1-RC1", f"payload={payload.get('release_id')};restore={restore.get('release_id')}"),
        ("PAYLOAD_GATE_PASS", payload.get("payload_status") == "PASS", str(payload.get("payload_status"))),
        ("PAYLOAD_EXISTS", payload_path.is_file(), str(payload_path)),
        ("PAYLOAD_HASH_CURRENT", actual_hash == payload.get("zip_sha256"), actual_hash),
        ("PAYLOAD_ENTRY_ACCOUNTING", payload.get("zip_entries") == payload.get("included_files", -1) + 1, f"entries={payload.get('zip_entries')};files={payload.get('included_files')}"),
        ("RESTORE_DRILL_PASS", restore.get("restore_drill") == "PASS", str(restore.get("restore_drill"))),
        ("RESTORE_CHECKS_COMPLETE", restore.get("checks_total") == restore.get("checks_passed") == 10, f"{restore.get('checks_passed')}/{restore.get('checks_total')}"),
        ("RESTORED_TESTS_PASS", restore.get("restored_tests") == "PASS", str(restore.get("restored_tests"))),
        ("RESTORE_HASH_MATCH", restore.get("payload_sha256") == actual_hash, str(restore.get("payload_sha256"))),
        ("TEMP_RESTORE_CLEANED", restore.get("temporary_restore_cleaned") is True, str(restore.get("temporary_restore_cleaned"))),
        ("NO_IMPLICIT_PROMOTION", not payload.get("git_commit_created") and not payload.get("git_tag_created") and not payload.get("deployment_performed") and not restore.get("git_commit_created") and not restore.get("git_tag_created") and not restore.get("deployment_performed"), "commit=false;tag=false;deployment=false"),
    ]
    audit = pd.DataFrame([{"check": name, "status": "PASS" if ok else "FAIL", "detail": detail} for name, ok, detail in checks])
    passed = bool(audit["status"].eq("PASS").all())
    audit_path, summary_path = Path(audit_csv), Path(summary_json)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    summary = {
        "phase": "V3.2.1 Phase 6.39",
        "release_id": "V3.2.1-RC1",
        "final_promotion_gate": "PASS" if passed else "FAIL",
        "promotion_state": "READY_AWAITING_EXPLICIT_APPROVAL" if passed else "HOLD",
        "checks_total": len(audit),
        "checks_passed": int(audit["status"].eq("PASS").sum()),
        "payload_zip": str(payload_path),
        "payload_sha256": actual_hash,
        "payload_files": payload.get("included_files"),
        "operator_approval_required": True,
        "git_commit_created": False,
        "git_tag_created": False,
        "deployment_performed": False,
        "audit_csv": str(audit_path),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "fail_closed": True,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not passed:
        failures = ", ".join(audit.loc[audit["status"].eq("FAIL"), "check"])
        raise ValueError(f"Phase 6.39 final promotion gate failed: {failures}")
    return summary | {"summary_json": str(summary_path)}
