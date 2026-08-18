from __future__ import annotations

from src.ml.phase558_not_applicable_integration_v321 import integrate_not_applicable_evidence_v321


def integrate_direct_action_evidence_v321(
    *, verification_csv: str, evidence_csv: str, output_csv: str,
    audit_csv: str, priority_output_csv: str, priority_summary_json: str,
) -> dict:
    result = integrate_not_applicable_evidence_v321(
        verification_csv=verification_csv, evidence_csv=evidence_csv,
        output_csv=output_csv, audit_csv=audit_csv,
        priority_output_csv=priority_output_csv,
        priority_summary_json=priority_summary_json,
        phase_label="V3.2.1 Phase 5.63",
    )
    return result | {"phase": "V3.2.1 Phase 5.63"}
