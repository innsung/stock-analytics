import hashlib
import json

import pytest

from src.ml.phase633_release_notes_v321 import build_release_notes_v321


def _handoff(tmp_path, tamper=False):
    evidence = {}
    for name in ("rc_manifest", "readiness_summary", "readiness_audit"):
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        evidence[name] = {"path": str(path), "sha256": hashlib.sha256(name.encode()).hexdigest()}
    if tamper:
        (tmp_path / "rc_manifest").write_text("changed", encoding="utf-8")
    payload = {"release_id": "V3.2.1-RC1", "handoff_status": "READY_FOR_OPERATOR_APPROVAL", "checks_total": 7, "checks_passed": 7, "source_evidence": evidence, "ledger": {"rows": 399, "status_counts": {"VERIFIED": 25, "NOT_APPLICABLE": 371, "UNRESOLVED": 3}, "actionable_rows": 0, "deferred_rows": 2, "blocked_rows": 1}, "git_commit_created": False, "git_tag_created": False, "deployment_performed": False}
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_builds_evidence_backed_release_notes(tmp_path):
    result = build_release_notes_v321(handoff_json=str(_handoff(tmp_path)), release_notes_md=str(tmp_path / "notes.md"), release_record_json=str(tmp_path / "record.json"))
    assert result["release_notes_status"] == "PASS"
    assert result["approval_state"] == "AWAITING_EXPLICIT_OPERATOR_APPROVAL"
    assert result["checks_passed"] == result["checks_total"] == 8


def test_release_notes_fail_closed_on_changed_evidence(tmp_path):
    with pytest.raises(ValueError, match="source_evidence_unchanged"):
        build_release_notes_v321(handoff_json=str(_handoff(tmp_path, tamper=True)), release_notes_md=str(tmp_path / "notes.md"), release_record_json=str(tmp_path / "record.json"))
