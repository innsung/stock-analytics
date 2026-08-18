import hashlib
import json

import pytest

from src.ml.phase639_final_promotion_gate_v321 import build_final_promotion_gate_v321


def _inputs(tmp_path, restore_status="PASS"):
    payload_zip = tmp_path / "payload.zip"
    payload_zip.write_bytes(b"payload")
    digest = hashlib.sha256(b"payload").hexdigest()
    payload = tmp_path / "payload.json"
    restore = tmp_path / "restore.json"
    payload.write_text(json.dumps({"release_id": "V3.2.1-RC1", "payload_status": "PASS", "payload_zip": str(payload_zip), "zip_sha256": digest, "zip_entries": 6, "included_files": 5, "git_commit_created": False, "git_tag_created": False, "deployment_performed": False}), encoding="utf-8")
    restore.write_text(json.dumps({"release_id": "V3.2.1-RC1", "restore_drill": restore_status, "checks_total": 10, "checks_passed": 10, "restored_tests": "PASS", "payload_sha256": digest, "temporary_restore_cleaned": True, "git_commit_created": False, "git_tag_created": False, "deployment_performed": False}), encoding="utf-8")
    return payload, restore


def test_final_gate_is_ready_awaiting_approval(tmp_path):
    payload, restore = _inputs(tmp_path)
    result = build_final_promotion_gate_v321(payload_summary_json=str(payload), restore_summary_json=str(restore), audit_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "summary.json"))
    assert result["final_promotion_gate"] == "PASS"
    assert result["promotion_state"] == "READY_AWAITING_EXPLICIT_APPROVAL"
    assert result["checks_passed"] == result["checks_total"] == 11


def test_final_gate_fails_closed_on_restore_failure(tmp_path):
    payload, restore = _inputs(tmp_path, restore_status="FAIL")
    with pytest.raises(ValueError, match="RESTORE_DRILL_PASS"):
        build_final_promotion_gate_v321(payload_summary_json=str(payload), restore_summary_json=str(restore), audit_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "summary.json"))
