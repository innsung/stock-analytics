from __future__ import annotations

from config.settings import get_settings
from src.dart.client import DartClient
from src.ml.phase549_spinoff_valuation_audit_v321 import audit_listed_spinoff_valuation_v321
from src.ml.phase550_spinoff_distribution_ledger_v321 import build_spinoff_distribution_ledger_v321
from src.ml.phase551_spinoff_fractional_settlement_v321 import audit_spinoff_fractional_settlement_v321
from src.ml.phase552_spinoff_evidence_completeness_v321 import audit_spinoff_evidence_completeness_v321
from src.ml.phase553_complex_action_coverage_gate_v321 import build_complex_action_coverage_gate_v321


SPINOFF_COMMANDS = frozenset(
    {
        "audit-listed-spinoff-valuation-v321",
        "build-spinoff-distribution-ledger-v321",
        "audit-spinoff-fractional-settlement-v321",
        "audit-spinoff-evidence-completeness-v321",
        "build-complex-action-coverage-gate-v321",
    }
)


def run_spinoff_command(args) -> None:
    if args.command not in SPINOFF_COMMANDS:
        raise ValueError(f"Unsupported spin-off command: {args.command}")

    if args.command == "audit-listed-spinoff-valuation-v321":
        try:
            get_settings()
            result = audit_listed_spinoff_valuation_v321(
                official_candidates_csv=args.official_candidates_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.49] {exc}")
        print("[V3.2.1 Phase 5.49 Listed Spin-off Valuation Audit]")
        print(f"Audited: {result['audited_rows']:,}")
        print(f"Parent price-series factor: {result['factor']:.12f}")
        print(f"Status: {result['audit_status']}")
        print(f"Audit: {result['output_csv']}")
    elif args.command == "build-spinoff-distribution-ledger-v321":
        try:
            result = build_spinoff_distribution_ledger_v321(
                valuation_audit_csv=args.valuation_audit_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.50] {exc}")
        print("[V3.2.1 Phase 5.50 Spin-off Distribution Ledger]")
        print(f"Events: {result['events']:,}")
        print(f"Ledger rows: {result['ledger_rows']:,}")
        print(f"Canonical total return ready: {result['canonical_total_return_ready']}")
        print(f"Ledger: {result['output_csv']}")
    elif args.command == "audit-spinoff-fractional-settlement-v321":
        try:
            result = audit_spinoff_fractional_settlement_v321(
                official_candidates_csv=args.official_candidates_csv,
                valuation_audit_csv=args.valuation_audit_csv,
                rule_output_csv=args.rule_output_csv,
                scenario_output_csv=args.scenario_output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.51] {exc}")
        print("[V3.2.1 Phase 5.51 Spin-off Fractional Settlement Audit]")
        print(f"Verified rules: {result['verified_rules']:,}")
        print(f"Scenarios: {result['scenario_rows']:,}")
        print(f"Canonical total return ready: {result['canonical_total_return_ready']}")
        print(f"Rule: {result['rule_output_csv']}")
        print(f"Scenarios: {result['scenario_output_csv']}")
    elif args.command == "audit-spinoff-evidence-completeness-v321":
        try:
            settings = get_settings()
            result = audit_spinoff_evidence_completeness_v321(
                DartClient(settings.dart_api_key),
                official_candidates_csv=args.official_candidates_csv,
                output_csv=args.output_csv,
                document_path=args.document_path,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.52] {exc}")
        print("[V3.2.1 Phase 5.52 Spin-off Evidence Completeness]")
        print(f"Checks: {result['checks']:,}")
        print(f"Verified: {result['verified']:,}")
        print(f"Missing: {result['missing']:,}")
        print(f"Canonical position transfer ready: {result['canonical_position_transfer_ready']}")
        print(f"Audit: {result['output_csv']}")
        print(f"Original document: {result['document_path']}")
    else:
        try:
            result = build_complex_action_coverage_gate_v321(
                base_coverage_json=args.base_coverage_json,
                evidence_audit_csv=args.evidence_audit_csv,
                output_json=args.output_json,
                audit_output_csv=args.audit_output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.53] {exc}")
        print("[V3.2.1 Phase 5.53 Complex Action Coverage Gate]")
        print(f"Gate status: {result['gate_status']}")
        print(f"Blockers: {result['blockers']:,}")
        print(f"Capital actions complete: {result['capital_actions_complete']}")
        print(f"Coverage complete: {result['coverage_complete']}")
        print(f"Guarded coverage: {result['output_json']}")
        print(f"Audit: {result['audit_output_csv']}")
