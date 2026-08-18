import json
import zipfile
from pathlib import Path

from src.ml.result_bundle_v321 import create_result_bundle_v321

def test_result_bundle_isolates_prefix_and_zips(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "run_a.csv").write_text("x\n1\n", encoding="utf-8")
    (source / "run_b.json").write_text('{"ok":true}', encoding="utf-8")
    (source / "other.csv").write_text("do not include", encoding="utf-8")
    target = tmp_path / "results" / "run_20260808"

    result = create_result_bundle_v321(
        output_prefix=str(source / "run"),
        result_dir=str(target),
        zip_results=True,
    )
    assert result["file_count"] == 2
    assert (target / "run_a.csv").exists()
    assert (target / "run_b.json").exists()
    assert not (target / "other.csv").exists()
    manifest = json.loads((target / "run_bundle_manifest.json").read_text(encoding="utf-8"))
    assert manifest["research_seen_through"] == "20260709"
    assert manifest["safety"]["credentials_included"] is False
    zp = Path(result["zip_path"])
    assert zp.exists()
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        assert any(n.endswith("/run_a.csv") for n in names)
        assert not any(n.endswith("/other.csv") for n in names)

def test_result_bundle_without_zip(tmp_path):
    (tmp_path / "x_one.csv").write_text("a\n", encoding="utf-8")
    out = tmp_path / "bundle"
    result = create_result_bundle_v321(
        output_prefix=str(tmp_path / "x"),
        result_dir=str(out),
        zip_results=False,
    )
    assert result["zip_path"] == ""
    assert (out / "x_one.csv").exists()


def test_result_bundle_fails_when_expected_outputs_missing(tmp_path):
    out = tmp_path / "empty"
    out.mkdir()
    try:
        create_result_bundle_v321(
            output_prefix=str(out / "run"),
            result_dir=str(out),
            zip_results=True,
            minimum_files=20,
        )
    except RuntimeError as exc:
        assert "실제 0개" in str(exc)
    else:
        raise AssertionError("empty diagnostic bundle must fail")
