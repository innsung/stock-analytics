import hashlib
import json
import zipfile

from src.ml.phase640_final_release_bundle_v321 import build_final_release_bundle_v321


def test_builds_sealed_final_release_bundle(tmp_path):
    payload_zip = tmp_path / "payload.zip"
    payload_zip.write_bytes(b"payload")
    digest = hashlib.sha256(b"payload").hexdigest()
    payload_summary = tmp_path / "payload.json"
    restore_summary = tmp_path / "restore.json"
    promotion_summary = tmp_path / "promotion.json"
    notes = tmp_path / "notes.md"
    payload_summary.write_text(json.dumps({"payload_status": "PASS", "zip_sha256": digest}), encoding="utf-8")
    restore_summary.write_text(json.dumps({"restore_drill": "PASS", "restored_tests": "PASS"}), encoding="utf-8")
    promotion_summary.write_text(json.dumps({"final_promotion_gate": "PASS", "promotion_state": "READY_AWAITING_EXPLICIT_APPROVAL", "git_commit_created": False, "git_tag_created": False, "deployment_performed": False}), encoding="utf-8")
    notes.write_text("notes", encoding="utf-8")
    result = build_final_release_bundle_v321(payload_zip=str(payload_zip), payload_summary_json=str(payload_summary), restore_summary_json=str(restore_summary), promotion_summary_json=str(promotion_summary), release_notes_md=str(notes), bundle_zip=str(tmp_path / "bundle.zip"), bundle_manifest_json=str(tmp_path / "manifest.json"), audit_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "summary.json"))
    assert result["final_bundle_status"] == "PASS"
    assert result["checks_passed"] == result["checks_total"] == 9
    with zipfile.ZipFile(tmp_path / "bundle.zip") as archive:
        assert archive.testzip() is None
        assert "FINAL_RELEASE_BUNDLE_MANIFEST.json" in archive.namelist()
