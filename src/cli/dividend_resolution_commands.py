from __future__ import annotations

import requests

from src.ml.phase575_ambiguous_kind_notice_resolution_v321 import resolve_ambiguous_kind_notice_v321
from src.ml.phase577_broadened_kind_notice_resolution_v321 import resolve_broadened_kind_notices_v321
from src.ml.phase578_pre_exdate_provenance_recovery_v321 import recover_pre_exdate_dividend_evidence_v321
from src.ml.phase579_explicit_no_dividend_resolution_v321 import resolve_explicit_no_dividend_v321


DIVIDEND_RESOLUTION_COMMANDS = frozenset(
    {
        "resolve-ambiguous-kind-notice-v321",
        "resolve-broadened-kind-notices-v321",
        "recover-pre-exdate-dividend-evidence-v321",
        "resolve-explicit-no-dividend-v321",
    }
)


def run_dividend_resolution_command(args) -> None:
    if args.command not in DIVIDEND_RESOLUTION_COMMANDS:
        raise ValueError(f"Unsupported dividend-resolution command: {args.command}")

    if args.command == "resolve-ambiguous-kind-notice-v321":
        try:
            result = resolve_ambiguous_kind_notice_v321(
                residual_csv=args.residual_csv,
                parsed_decisions_csv=args.parsed_decisions_csv,
                discovery_output_csv=args.discovery_output_csv,
                candidate_audit_csv=args.candidate_audit_csv,
                strict_evidence_csv=args.strict_evidence_csv,
                strict_audit_csv=args.strict_audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.75] {exc}")
        print("[V3.2.1 Phase 5.75 Ambiguous KIND Notice Resolution]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Uniquely resolved: {result['resolved_rows']:,}")
        print(f"Strict evidence: {result['strict_rows']:,}")
        print(f"Status: {result['status']}")
        print(f"Output: {result['discovery_output_csv']}")
    elif args.command == "resolve-broadened-kind-notices-v321":
        try:
            result = resolve_broadened_kind_notices_v321(
                residual_csv=args.residual_csv,
                prior_discovery_audit_csv=args.prior_discovery_audit_csv,
                candidates_csv=args.candidates_csv,
                parsed_decisions_csv=args.parsed_decisions_csv,
                discovery_output_csv=args.discovery_output_csv,
                candidate_audit_csv=args.candidate_audit_csv,
                strict_evidence_csv=args.strict_evidence_csv,
                strict_audit_csv=args.strict_audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.77] {exc}")
        print("[V3.2.1 Phase 5.77 Broadened KIND Notice Resolution]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Resolved: {result['resolved_rows']:,}")
        print(f"Strict evidence: {result['strict_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['discovery_output_csv']}")
    elif args.command == "recover-pre-exdate-dividend-evidence-v321":
        try:
            result = recover_pre_exdate_dividend_evidence_v321(
                residual_csv=args.residual_csv,
                parsed_decisions_csv=args.parsed_decisions_csv,
                candidates_csv=args.candidates_csv,
                provenance_audit_csv=args.provenance_audit_csv,
                discovery_output_csv=args.discovery_output_csv,
                discovery_audit_csv=args.discovery_audit_csv,
                strict_evidence_csv=args.strict_evidence_csv,
                strict_audit_csv=args.strict_audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.78] {exc}")
        print("[V3.2.1 Phase 5.78 Pre-ex-date Provenance Recovery]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Early provenance recovered: {result['provenance_recovered_rows']:,}")
        print(f"No pre-ex-date disclosure: {result['no_pre_exdate_disclosure_rows']:,}")
        print(f"Official notices resolved: {result['official_notices_resolved']:,}")
        print(f"Strict evidence: {result['strict_rows']:,}")
        print(f"Output: {result['provenance_audit_csv']}")
    else:
        try:
            result = resolve_explicit_no_dividend_v321(
                residual_csv=args.residual_csv,
                dividend_facts_csv=args.dividend_facts_csv,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                business_year=args.business_year,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.79] {exc}")
        print("[V3.2.1 Phase 5.79 Explicit No-dividend Resolution]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
