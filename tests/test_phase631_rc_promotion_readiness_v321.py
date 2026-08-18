import hashlib
import json

import pandas as pd
import pytest

from src.ml.phase631_rc_promotion_readiness_v321 import build_rc_promotion_readiness_v321


def _manifest(tmp_path):
    artifacts = {}
    for name in ("canonical_ledger", "release_zip", "requirements", "requirements_lock"):
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        artifacts[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(name.encode()).hexdigest(),
            "size_bytes": len(name.encode()),
        }
    payload = {
        "release_id": "V3.2.1-RC1",
        "seal_status": "PASS",
        "checks_total": 9,
        "checks_passed": 9,
        "ledger": {"rows": 399, "status_counts": {"VERIFIED": 25, "NOT_APPLICABLE": 371, "UNRESOLVED": 3}, "actionable_rows": 0, "deferred_rows": 2, "blocked_rows": 1},
        "artifacts": artifacts,
        "gates": {name: {"status": "PASS"} for name in ("QUALITY", "INTEGRITY", "RESTORE", "RUNTIME")},
        "git_tag_created": False,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, artifacts


def test_rc_is_promotion_ready_when_seal_is_unchanged(tmp_path):
    manifest, _ = _manifest(tmp_path)
    result = build_rc_promotion_readiness_v321(manifest_json=str(manifest), audit_output_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "summary.json"))
    assert result["promotion_state"] == "PROMOTION_READY"
    assert result["checks_passed"] == result["checks_total"] == 12
    assert pd.read_csv(tmp_path / "audit.csv")["status"].eq("PASS").all()


def test_rc_is_held_when_sealed_artifact_changes(tmp_path):
    manifest, artifacts = _manifest(tmp_path)
    with open(artifacts["requirements"]["path"], "a", encoding="utf-8") as handle:
        handle.write("changed")
    with pytest.raises(ValueError, match="SEALED_ARTIFACT_REQUIREMENTS"):
        build_rc_promotion_readiness_v321(manifest_json=str(manifest), audit_output_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "summary.json"))
