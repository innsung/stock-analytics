import pandas as pd

from src.ml.phase586_historical_chain_consolidation_v321 import consolidate_historical_legal_chains_v321


def test_consolidates_children_and_preserves_latest_amendment_as_control(tmp_path):
    pd.DataFrame([
        {"queue_event_id": "a1", "code": "006400", "document_role": "AMENDMENT",
         "mechanic_family": "RIGHTS_OFFERING", "child_rcept_no": "child1",
         "parent_queue_event_id": "p1", "parent_rcept_no": "parent",
         "semantic_validation_status": "SEMANTIC_CHAIN_CONFIRMED_REVIEW_REQUIRED"},
        {"queue_event_id": "a2", "code": "006400", "document_role": "AMENDMENT",
         "mechanic_family": "RIGHTS_OFFERING", "child_rcept_no": "child2",
         "parent_queue_event_id": "p1", "parent_rcept_no": "parent",
         "semantic_validation_status": "SEMANTIC_CHAIN_CONFIRMED_REVIEW_REQUIRED"},
    ]).to_csv(tmp_path / "validation.csv", index=False)
    pd.DataFrame([{"queue_event_id": "a1", "source_reference_date": "20240120"},
                  {"queue_event_id": "a2", "source_reference_date": "20240130"}]).to_csv(
                      tmp_path / "chain.csv", index=False)
    result = consolidate_historical_legal_chains_v321(
        validation_csv=str(tmp_path / "validation.csv"), chain_csv=str(tmp_path / "chain.csv"),
        group_output_csv=str(tmp_path / "groups.csv"), evidence_output_csv=str(tmp_path / "evidence.csv"),
        audit_output_csv=str(tmp_path / "audit.csv"), summary_json=str(tmp_path / "summary.json"))
    group = pd.read_csv(tmp_path / "groups.csv", dtype=str).iloc[0]
    assert result["not_applicable_evidence_rows"] == 2
    assert group["controlling_mechanics_rcept_no"] == "child2"
    assert group["group_status"] == "PRIMARY_MECHANICS_UNRESOLVED_CONTROLLING_DOCUMENT_PRESERVED"
    assert set(pd.read_csv(tmp_path / "evidence.csv")["queue_event_id"]) == {"a1", "a2"}
