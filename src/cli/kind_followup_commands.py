from __future__ import annotations

from src.ml.phase533_kind_batch_market_search_v321 import discover_kind_market_notices_batch_v321
from src.ml.phase534_kind_dividend_decision_pairing_v321 import acquire_paired_kind_dividend_decisions_v321
from src.ml.phase535_kind_paired_strict_evidence_v321 import build_paired_kind_market_observations_v321
from src.ml.phase537_kind_direct_decision_acquisition_v321 import acquire_direct_kind_dividend_decisions_v321
from src.ml.phase538_kind_aggregate_notice_extractor_v321 import extract_kind_aggregate_market_targets_v321


KIND_FOLLOWUP_COMMANDS = frozenset(
    {
        "discover-kind-market-notices-batch-v321",
        "acquire-paired-kind-dividend-decisions-v321",
        "build-paired-kind-market-observations-v321",
        "acquire-direct-kind-dividend-decisions-v321",
        "extract-kind-aggregate-market-targets-v321",
    }
)


def run_kind_followup_command(args) -> None:
    if args.command not in KIND_FOLLOWUP_COMMANDS:
        raise ValueError(f"Unsupported KIND follow-up command: {args.command}")

    if args.command == "discover-kind-market-notices-batch-v321":
        try:
            result = discover_kind_market_notices_batch_v321(
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                search_start=args.search_start,
                search_end=args.search_end,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.33] {exc}")
        print("[V3.2.1 Phase 5.33 KIND Batch Market Search]")
        print(f"Target codes: {result['target_codes']:,}")
        print(f"Matched notices: {result['matched_notices']:,}")
        print(f"Discovered common notices: {result['discovered_common_notices']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "acquire-paired-kind-dividend-decisions-v321":
        try:
            result = acquire_paired_kind_dividend_decisions_v321(
                notices_csv=args.notices_csv,
                decision_disclosures_csv=args.decision_disclosures_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.34] {exc}")
        print("[V3.2.1 Phase 5.34 KIND Dividend Decision Pairing]")
        print(f"Market notices: {result['notice_rows']:,}")
        print(f"Acquired documents: {result['acquired_documents']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Documents: {result['documents_dir']}")
    elif args.command == "build-paired-kind-market-observations-v321":
        try:
            result = build_paired_kind_market_observations_v321(
                pairing_csv=args.pairing_csv,
                parsed_decisions_csv=args.parsed_decisions_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.35] {exc}")
        print("[V3.2.1 Phase 5.35 KIND Paired Market Evidence]")
        print(f"Paired rows: {result['paired_rows']:,}")
        print(f"Valid observations: {result['valid_observations']:,}")
        print(f"Invalid rows: {result['invalid_rows']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "acquire-direct-kind-dividend-decisions-v321":
        try:
            result = acquire_direct_kind_dividend_decisions_v321(
                manifest_csv=args.manifest_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.37] {exc}")
        print("[V3.2.1 Phase 5.37 KIND Direct Decision Acquisition]")
        print(f"Manifest rows: {result['manifest_rows']:,}")
        print(f"Acquired documents: {result['acquired_documents']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Documents: {result['documents_dir']}")
    else:
        try:
            result = extract_kind_aggregate_market_targets_v321(
                aggregate_manifest_csv=args.aggregate_manifest_csv,
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.38] {exc}")
        print("[V3.2.1 Phase 5.38 KIND Aggregate Market Notice]")
        print(f"Aggregate sources: {result['source_rows']:,}")
        print(f"Matched targets: {result['matched_targets']:,}")
        print(f"Matched codes: {result['matched_codes']}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
