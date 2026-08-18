import json
import pandas as pd

from src.ml.phase553_complex_action_coverage_gate_v321 import build_complex_action_coverage_gate_v321


def test_missing_complex_evidence_overrides_incorrect_complete_flags(tmp_path):
    base, evidence = tmp_path / "base.json", tmp_path / "e.csv"
    output, audit = tmp_path / "guarded.json", tmp_path / "audit.csv"
    base.write_text(json.dumps({"cash_distributions_complete": True,
        "capital_actions_complete": True, "complete": True}), encoding="utf-8")
    pd.DataFrame([
        {"rcept_no": "r", "check_item": "RATIO", "evidence_status": "VERIFIED"},
        {"rcept_no": "r", "check_item": "SURVIVING_RULE", "evidence_status": "MISSING"},
    ]).to_csv(evidence, index=False)
    result = build_complex_action_coverage_gate_v321(
        base_coverage_json=str(base), evidence_audit_csv=str(evidence),
        output_json=str(output), audit_output_csv=str(audit))
    guarded = json.loads(output.read_text(encoding="utf-8"))
    assert result["gate_status"] == "BLOCKED"
    assert guarded["capital_actions_complete"] is False
    assert guarded["complete"] is False
    assert guarded["complex_action_blockers"] == 1


def test_all_verified_preserves_existing_coverage_state(tmp_path):
    base, evidence = tmp_path / "base.json", tmp_path / "e.csv"
    base.write_text(json.dumps({"cash_distributions_complete": False,
        "capital_actions_complete": False, "complete": False}), encoding="utf-8")
    pd.DataFrame([{"rcept_no": "r", "check_item": "X",
        "evidence_status": "VERIFIED"}]).to_csv(evidence, index=False)
    result = build_complex_action_coverage_gate_v321(
        base_coverage_json=str(base), evidence_audit_csv=str(evidence),
        output_json=str(tmp_path / "o.json"), audit_output_csv=str(tmp_path / "a.csv"))
    assert result["gate_status"] == "PASS"
    assert result["capital_actions_complete"] is False
