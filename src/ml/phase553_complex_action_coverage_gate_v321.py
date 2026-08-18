from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def build_complex_action_coverage_gate_v321(
    *, base_coverage_json: str, evidence_audit_csv: str,
    output_json: str, audit_output_csv: str,
) -> dict:
    base_path = Path(base_coverage_json)
    if not base_path.exists():
        raise FileNotFoundError(f"base coverage JSON unavailable: {base_path}")
    coverage = json.loads(base_path.read_text(encoding="utf-8"))
    required = {"cash_distributions_complete", "capital_actions_complete", "complete"}
    missing_fields = required - set(coverage)
    if missing_fields:
        raise ValueError("base coverage missing fields: " + ", ".join(sorted(missing_fields)))

    evidence = pd.read_csv(evidence_audit_csv, dtype=str).fillna("")
    required_evidence = {"rcept_no", "check_item", "evidence_status"}
    missing_columns = required_evidence - set(evidence.columns)
    if missing_columns:
        raise ValueError("evidence audit missing columns: " + ", ".join(sorted(missing_columns)))
    blockers = evidence[~evidence["evidence_status"].eq("VERIFIED")].copy()
    blocker_rows = []
    for row in blockers.itertuples(index=False):
        blocker_rows.append({
            "rcept_no": row.rcept_no, "check_item": row.check_item,
            "evidence_status": row.evidence_status,
            "gate_decision": "BLOCK_CAPITAL_ACTION_COVERAGE",
        })
    complex_complete = len(blocker_rows) == 0
    if not complex_complete:
        coverage["capital_actions_complete"] = False
        coverage["complete"] = False
    coverage["complex_actions_complete"] = complex_complete
    coverage["complex_action_blockers"] = len(blocker_rows)
    coverage["complex_action_gate_source"] = str(Path(evidence_audit_csv))
    coverage["coverage_gate_status"] = "PASS" if complex_complete else "BLOCKED"

    output = Path(output_json); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    audit = pd.DataFrame(blocker_rows, columns=[
        "rcept_no", "check_item", "evidence_status", "gate_decision"])
    audit_path = Path(audit_output_csv); audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    return {"gate_status": coverage["coverage_gate_status"],
            "blockers": len(blocker_rows), "capital_actions_complete": bool(coverage["capital_actions_complete"]),
            "coverage_complete": bool(coverage["complete"]),
            "output_json": str(output), "audit_output_csv": str(audit_path)}
