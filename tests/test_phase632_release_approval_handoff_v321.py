import json

import pandas as pd
import pytest

from src.ml.phase632_release_approval_handoff_v321 import build_release_approval_handoff_v321


def _inputs(tmp_path, state="PROMOTION_READY"):
    manifest = tmp_path / "manifest.json"
    readiness = tmp_path / "readiness.json"
    audit = tmp_path / "audit.csv"
    manifest.write_text(json.dumps({"release_id": "V3.2.1-RC1", "seal_status": "PASS", "ledger": {"actionable_rows": 0, "deferred_rows": 2, "blocked_rows": 1}, "git_tag_created": False}), encoding="utf-8")
    readiness.write_text(json.dumps({"release_id": "V3.2.1-RC1", "promotion_state": state, "checks_total": 12, "checks_passed": 12, "git_commit_created": False, "git_tag_created": False}), encoding="utf-8")
    pd.DataFrame({"status": ["PASS"] * 12}).to_csv(audit, index=False)
    return manifest, readiness, audit


def test_builds_operator_approval_handoff(tmp_path):
    manifest, readiness, audit = _inputs(tmp_path)
    result = build_release_approval_handoff_v321(rc_manifest_json=str(manifest), readiness_summary_json=str(readiness), readiness_audit_csv=str(audit), handoff_json=str(tmp_path / "handoff.json"), checklist_md=str(tmp_path / "checklist.md"))
    assert result["handoff_status"] == "READY_FOR_OPERATOR_APPROVAL"
    assert result["checks_passed"] == result["checks_total"] == 7
    assert result["git_tag_created"] is False


def test_holds_when_rc_is_not_promotion_ready(tmp_path):
    manifest, readiness, audit = _inputs(tmp_path, state="HOLD")
    with pytest.raises(ValueError, match="promotion_ready"):
        build_release_approval_handoff_v321(rc_manifest_json=str(manifest), readiness_summary_json=str(readiness), readiness_audit_csv=str(audit), handoff_json=str(tmp_path / "handoff.json"), checklist_md=str(tmp_path / "checklist.md"))
