from __future__ import annotations


def register_spinoff_parsers(sub) -> None:
    p = sub.add_parser("audit-listed-spinoff-valuation-v321")
    p.add_argument("--official-candidates-csv", default="data/raw/v321/events/official_candidates/official_event_candidates_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/listed_spinoff_valuation_audit_phase549_v321.csv")
    p = sub.add_parser("build-spinoff-distribution-ledger-v321")
    p.add_argument("--valuation-audit-csv", default="data/raw/v321/events/listed_spinoff_valuation_audit_phase549_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/spinoff_distribution_ledger_phase550_v321.csv")
    p = sub.add_parser("audit-spinoff-fractional-settlement-v321")
    p.add_argument("--official-candidates-csv", default="data/raw/v321/events/official_candidates/official_event_candidates_v321.csv")
    p.add_argument("--valuation-audit-csv", default="data/raw/v321/events/listed_spinoff_valuation_audit_phase549_v321.csv")
    p.add_argument("--rule-output-csv", default="data/raw/v321/events/spinoff_fractional_rule_phase551_v321.csv")
    p.add_argument("--scenario-output-csv", default="data/raw/v321/events/spinoff_fractional_scenarios_phase551_v321.csv")
    p = sub.add_parser("audit-spinoff-evidence-completeness-v321")
    p.add_argument("--official-candidates-csv", default="data/raw/v321/events/official_candidates/official_event_candidates_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/spinoff_evidence_completeness_phase552_v321.csv")
    p.add_argument("--document-path", default="data/raw/v321/events/corporate_action_documents_phase552/20250822000109.xml")
    p = sub.add_parser("build-complex-action-coverage-gate-v321")
    p.add_argument("--base-coverage-json", default="data/v321_foundation/total_return_coverage_v321.json")
    p.add_argument("--evidence-audit-csv", default="data/raw/v321/events/spinoff_evidence_completeness_phase552_v321.csv")
    p.add_argument("--output-json", default="data/v321_foundation/total_return_coverage_guarded_phase553_v321.json")
    p.add_argument("--audit-output-csv", default="data/raw/v321/events/complex_action_coverage_gate_phase553_v321.csv")
