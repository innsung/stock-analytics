from src.ml.phase634_repository_promotion_preflight_v321 import classify_release_path


def test_classifies_release_candidates_and_evidence():
    assert classify_release_path("src/ml/model.py")[0] == "RELEASE_CANDIDATE"
    assert classify_release_path("tests/test_model.py")[0] == "RELEASE_CANDIDATE"
    assert classify_release_path("data/raw/v321/events/audit.csv")[0] == "EVIDENCE_REVIEW"
    assert classify_release_path("requirements-lock.txt")[0] == "RELEASE_CANDIDATE"


def test_classifies_runtime_and_generated_artifacts():
    assert classify_release_path(".venv312/Lib/site.py")[0] == "EXCLUDE_RUNTIME"
    assert classify_release_path("tmp/cache.bin")[0] == "EXCLUDE_RUNTIME"
    assert classify_release_path("results.csv")[0] == "EXCLUDE_GENERATED"
    assert classify_release_path("archive.zip")[0] == "EXCLUDE_GENERATED"
