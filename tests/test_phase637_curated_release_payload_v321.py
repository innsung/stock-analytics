import json
import zipfile

from src.ml.phase637_curated_release_payload_v321 import build_curated_release_payload_v321


def test_builds_curated_payload_with_preserved_paths(tmp_path):
    for relative, content in (("src/app.py", "x=1"), ("tests/test_app.py", "def test_x(): pass"), ("docs/readme.md", "docs")):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pandas", encoding="utf-8")
    resolution = tmp_path / "resolution.json"
    resolution.write_text(json.dumps({"curation_resolution": "PASS", "remaining_manual_review": 0}), encoding="utf-8")
    result = build_curated_release_payload_v321(repository=str(tmp_path), resolution_summary_json=str(resolution), payload_zip=str(tmp_path / "payload.zip"), manifest_csv=str(tmp_path / "manifest.csv"), summary_json=str(tmp_path / "summary.json"))
    assert result["payload_status"] == "PASS"
    assert result["included_files"] == 4
    with zipfile.ZipFile(tmp_path / "payload.zip") as archive:
        assert "src/app.py" in archive.namelist()
        assert "RELEASE_PAYLOAD_MANIFEST.csv" in archive.namelist()


def test_payload_excludes_runtime_and_live_config(tmp_path):
    (tmp_path / "src" / "__pycache__").mkdir(parents=True)
    (tmp_path / "src" / "__pycache__" / "app.pyc").write_bytes(b"cache")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "valuation_snapshots_v321.csv").write_text("placeholder", encoding="utf-8")
    resolution = tmp_path / "resolution.json"
    resolution.write_text(json.dumps({"curation_resolution": "PASS", "remaining_manual_review": 0}), encoding="utf-8")
    result = build_curated_release_payload_v321(repository=str(tmp_path), resolution_summary_json=str(resolution), payload_zip=str(tmp_path / "payload.zip"), manifest_csv=str(tmp_path / "manifest.csv"), summary_json=str(tmp_path / "summary.json"))
    assert result["included_files"] == 0
    assert result["excluded_files"] == 2
