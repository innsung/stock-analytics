from src.ml.phase636_manual_curation_resolution_v321 import resolve_manual_curation_path


def test_resolves_duplicate_placeholder_config(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    content = b"code,value\n005930,1\n"
    (config / "valuation_snapshots_v321.csv").write_bytes(content)
    (config / "valuation_snapshots_v321.template.csv").write_bytes(content)
    decision, _, replacement = resolve_manual_curation_path(tmp_path, "config/valuation_snapshots_v321.csv")
    assert decision == "EXCLUDE_DUPLICATE_TEMPLATE"
    assert replacement.endswith(".template.csv")


def test_resolves_superseded_phase_backup(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.py.phase516bak").write_text("old", encoding="utf-8")
    (source / "main.py").write_text("new and tested", encoding="utf-8")
    decision, _, replacement = resolve_manual_curation_path(tmp_path, "src/main.py.phase516bak")
    assert decision == "EXCLUDE_SUPERSEDED_BACKUP"
    assert replacement == "src/main.py"


def test_unknown_manual_item_remains_unresolved(tmp_path):
    (tmp_path / "unknown.txt").write_text("x", encoding="utf-8")
    assert resolve_manual_curation_path(tmp_path, "unknown.txt")[0] == "MANUAL_REVIEW"
