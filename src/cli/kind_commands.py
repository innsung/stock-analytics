from __future__ import annotations

from src.ml.phase516_kind_crosscheck_v321 import crosscheck_kind_dividend_disclosures_v321
from src.ml.phase518_kind_retry_v321 import build_kind_retry_queue_v321
from src.ml.phase526_kind_document_parser_v321 import parse_kind_dividend_documents_v321
from src.ml.phase527_kind_reconciliation_v321 import reconcile_kind_dividend_candidates_v321
from src.ml.phase528_kind_market_exdate_v321 import acquire_kind_market_exdates_v321
from src.ml.phase529_kind_market_search_v321 import discover_kind_market_exdate_notices_v321


KIND_COMMANDS = frozenset(
    {
        "crosscheck-kind-dividends-v321",
        "retry-kind-dividends-v321",
        "parse-kind-dividends-v321",
        "reconcile-kind-dividends-v321",
        "acquire-kind-market-exdates-v321",
        "discover-kind-market-exdates-v321",
    }
)


def run_kind_command(args) -> None:
    if args.command not in KIND_COMMANDS:
        raise ValueError(f"Unsupported KIND command: {args.command}")

    if args.command == "crosscheck-kind-dividends-v321":
        try:
            result = crosscheck_kind_dividend_disclosures_v321(
                market_exdate_queue_csv=args.market_exdate_queue_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                timeout_seconds=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.16] {exc}")
        print("[V3.2.1 Phase 5.16 KRX KIND Dividend Cross-check]")
        print(f"P1 rows: {result['p1_rows']:,}")
        print(f"KIND success: {result['kind_success']:,}")
        print(f"Record-date matches: {result['record_matches']:,}")
        print(f"Cash-amount matches: {result['amount_matches']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
        print("KIND 교차검증도 아직 EX_DATE evidence는 아닙니다.")
    elif args.command == "retry-kind-dividends-v321":
        try:
            result = build_kind_retry_queue_v321(
                crosscheck_csv=args.crosscheck_csv,
                audit_csv=args.audit_csv,
                retry_queue_csv=args.retry_queue_csv,
                output_csv=args.output_csv,
                documents_dir=args.documents_dir,
                timeout=args.timeout_seconds,
                live_fetch=not args.dry_run,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.18] {exc}")
        print("[V3.2.1 Phase 5.18 KIND Retry]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Retry rows: {result['retry_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Audit: {result['audit_csv']}")
        print(f"Retry queue: {result['retry_queue_csv']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "parse-kind-dividends-v321":
        try:
            result = parse_kind_dividend_documents_v321(
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.26] {exc}")
        print("[V3.2.1 Phase 5.26 KIND Document Parser]")
        print(f"Documents: {result['documents']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "reconcile-kind-dividends-v321":
        try:
            result = reconcile_kind_dividend_candidates_v321(
                market_queue_csv=args.market_queue_csv,
                crosscheck_csv=args.crosscheck_csv,
                parsed_csv=args.parsed_csv,
                audit_csv=args.audit_csv,
                official_facts_csv=args.official_facts_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.27] {exc}")
        print("[V3.2.1 Phase 5.27 KIND Reconciliation]")
        print(f"Candidate rows: {result['candidate_rows']:,}")
        print(f"Candidate statuses: {result['candidate_status_counts']}")
        print(f"Official facts: {result['official_fact_rows']:,}")
        print(f"Audit: {result['audit_csv']}")
        print(f"Official facts output: {result['official_facts_csv']}")
    elif args.command == "acquire-kind-market-exdates-v321":
        try:
            result = acquire_kind_market_exdates_v321(
                manifest_csv=args.manifest_csv,
                official_facts_csv=args.official_facts_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.28] {exc}")
        print("[V3.2.1 Phase 5.28 KIND Market Ex-date Acquisition]")
        print(f"Manifest rows: {result['manifest_rows']:,}")
        print(f"Acquired rows: {result['acquired_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
    else:
        try:
            result = discover_kind_market_exdate_notices_v321(
                candidates_csv=args.candidates_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                timeout=args.timeout_seconds,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.29] {exc}")
        print("[V3.2.1 Phase 5.29 KIND Market Ex-date Discovery]")
        print(f"Candidates: {result['candidate_rows']:,}")
        print(f"Discovered: {result['discovered_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {args.output_csv}")
        print(f"Audit: {args.audit_csv}")
