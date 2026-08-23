from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.phase583_periodic_dividend_aggregate_quarantine_v321 import quarantine_periodic_dividend_aggregates_v321
from src.ml.phase584_historical_legal_event_chain_v321 import build_historical_legal_event_chain_v321
from src.ml.phase585_historical_chain_document_validation_v321 import validate_historical_chain_documents_v321
from src.ml.phase586_historical_chain_consolidation_v321 import consolidate_historical_legal_chains_v321


HISTORICAL_CHAIN_COMMANDS = frozenset(
    {
        "quarantine-periodic-dividend-aggregates-v321",
        "build-historical-legal-event-chain-v321",
        "validate-historical-chain-documents-v321",
        "consolidate-historical-legal-chains-v321",
    }
)


def run_historical_chain_command(settings, args) -> None:
    if args.command not in HISTORICAL_CHAIN_COMMANDS:
        raise ValueError(f"Unsupported historical-chain command: {args.command}")

    if args.command == "quarantine-periodic-dividend-aggregates-v321":
        try:
            result = quarantine_periodic_dividend_aggregates_v321(
                execution_manifest_csv=args.execution_manifest_csv,
                dividend_facts_csv=args.dividend_facts_csv,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                replacement_queue_csv=args.replacement_queue_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.83] {exc}")
        print("[V3.2.1 Phase 5.83 Periodic Dividend Aggregate Quarantine]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Quarantined placeholders: {result['quarantined_not_applicable_rows']:,}")
        print(f"Validation failed: {result['validation_failed_rows']:,}")
        print(f"Replacement requirements: {result['replacement_requirements']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "build-historical-legal-event-chain-v321":
        try:
            result = build_historical_legal_event_chain_v321(
                execution_manifest_csv=args.execution_manifest_csv,
                disclosures_csv=args.disclosures_csv,
                output_csv=args.output_csv,
                review_queue_csv=args.review_queue_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.84] {exc}")
        print("[V3.2.1 Phase 5.84 Historical Legal Event Chain]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Unique child receipts: {result['unique_child_receipts']:,}")
        print(f"Ready for semantic validation: {result['ready_for_semantic_validation']:,}")
        print(f"Manual review: {result['manual_review_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "validate-historical-chain-documents-v321":
        try:
            result = validate_historical_chain_documents_v321(
                DartClient(settings.dart_api_key),
                chain_csv=args.chain_csv,
                execution_manifest_csv=args.execution_manifest_csv,
                disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
                review_queue_csv=args.review_queue_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.85] {exc}")
        print("[V3.2.1 Phase 5.85 Historical Chain Document Validation]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Unique receipts processed: {result['unique_receipts_processed']:,}")
        print(f"Semantic chains confirmed: {result['semantic_chains_confirmed']:,}")
        print(f"Review rows: {result['semantic_or_acquisition_review_rows']:,}")
        print(f"Output: {result['output_csv']}")
    else:
        try:
            result = consolidate_historical_legal_chains_v321(
                validation_csv=args.validation_csv,
                chain_csv=args.chain_csv,
                group_output_csv=args.group_output_csv,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.86] {exc}")
        print("[V3.2.1 Phase 5.86 Historical Chain Consolidation]")
        print(f"Confirmed children: {result['confirmed_child_rows']:,}")
        print(f"Legal event groups: {result['consolidated_legal_event_groups']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Primary events resolved: {result['primary_events_resolved']:,}")
        print(f"Output: {result['group_output_csv']}")
