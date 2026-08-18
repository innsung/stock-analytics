from src.ml.phase635_release_curation_manifest_v321 import classify_curation_path


def test_allowlists_release_sources_and_safe_metadata():
    assert classify_curation_path("src/ml/model.py")[0] == "PROPOSE_INCLUDE"
    assert classify_curation_path("database/database.py")[0] == "PROPOSE_INCLUDE"
    assert classify_curation_path("tests/test_model.py")[0] == "PROPOSE_INCLUDE"
    assert classify_curation_path("docs/release.md")[0] == "PROPOSE_INCLUDE"
    assert classify_curation_path("config/example.template.csv")[0] == "PROPOSE_INCLUDE"
    assert classify_curation_path("requirements.txt")[0] == "PROPOSE_INCLUDE"
    assert classify_curation_path("V3_2_1_RELEASE.md")[0] == "PROPOSE_INCLUDE"


def test_requires_review_or_excludes_unsafe_paths():
    assert classify_curation_path("config/valuation_snapshots_v321.csv")[0] == "MANUAL_REVIEW"
    assert classify_curation_path("src/__pycache__/model.pyc")[0] == "PROPOSE_EXCLUDE"
    assert classify_curation_path("notes.txt")[0] == "PROPOSE_INCLUDE"
