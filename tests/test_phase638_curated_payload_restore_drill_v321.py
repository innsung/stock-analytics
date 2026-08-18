import hashlib
import json
import zipfile

import pandas as pd
import pytest

from src.ml.phase638_curated_payload_restore_drill_v321 import verify_curated_payload_restore_v321


def _payload(tmp_path, corrupt=False):
    source = tmp_path / "source.txt"
    source.write_text("ok", encoding="utf-8")
    digest = hashlib.sha256(b"ok").hexdigest()
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"path": "source.txt", "size_bytes": 2, "sha256": "bad" if corrupt else digest}]).to_csv(manifest, index=False)
    payload = tmp_path / "payload.zip"
    with zipfile.ZipFile(payload, "w") as archive:
        archive.write(source, "source.txt")
        archive.write(manifest, "RELEASE_PAYLOAD_MANIFEST.csv")
    summary = tmp_path / "expected.json"
    summary.write_text(json.dumps({"release_id": "V3.2.1-RC1", "zip_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(), "zip_entries": 2, "included_files": 1}), encoding="utf-8")
    return payload, summary


def test_restores_and_verifies_curated_payload(tmp_path):
    payload, expected = _payload(tmp_path)
    result = verify_curated_payload_restore_v321(payload_zip=str(payload), expected_summary_json=str(expected), audit_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "summary.json"), run_tests=False)
    assert result["restore_drill"] == "PASS"
    assert result["temporary_restore_cleaned"] is True


def test_restore_drill_fails_on_manifest_mismatch(tmp_path):
    payload, expected = _payload(tmp_path, corrupt=True)
    with pytest.raises(ValueError, match="RESTORED_FILE_INTEGRITY"):
        verify_curated_payload_restore_v321(payload_zip=str(payload), expected_summary_json=str(expected), audit_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "summary.json"), run_tests=False)
