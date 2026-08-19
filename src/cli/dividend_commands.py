from __future__ import annotations

import sqlite3

from src.dart.client import DartClient
from src.ml.benchmark_etf_distribution_v321 import (
    inject_benchmark_etf_events_v321,
    prepare_benchmark_etf_distribution_template_v321,
    summarize_stock_dividend_resolution_v321,
    validate_benchmark_etf_distributions_v321,
)
from src.ml.cash_distribution_v321 import (
    build_stock_cash_amount_candidates_v321,
    compare_cash_amount_candidates_v321,
    prepare_official_cash_event_template_v321,
    validate_official_cash_events_v321,
)
from src.ml.kodex_distribution_acquisition_v321 import (
    acquire_kodex_distribution_candidates_v321,
    build_stock_dividend_ambiguity_report_v321,
)
from src.ml.kodex_dynamic_discovery_v321 import (
    discover_kodex_dynamic_endpoints_v321,
    refine_stock_dividend_candidates_v321,
)
from src.ml.phase512_resolvers_v321 import (
    acquire_stock_dividend_decision_disclosures_v321,
    build_stock_dividend_exdate_resolution_queue_v321,
    rank_and_probe_kodex_endpoints_v321,
)
from src.ml.phase513_parsers_v321 import (
    extract_dart_dividend_record_dates_v321,
    inspect_kodex_probe_responses_v321,
    merge_dividend_amount_and_record_candidates_v321,
)
from src.ml.phase514_strict_exdate_v321 import (
    build_explicit_stock_exdate_strict_evidence_v321,
    build_record_date_calendar_candidates_v321,
    export_benchmark_calendar_from_db_v321,
    parse_kodex_distribution_tables_v321,
)
from src.ml.phase515_market_exdate_v321 import (
    build_market_exdate_verification_queue_v321,
    summarize_kodex_high_signal_bodies_v321,
    validate_official_market_exdates_v321,
)


DIVIDEND_COMMANDS = frozenset({
    "build-stock-cash-amount-candidates-v321",
    "prepare-official-cash-events-v321",
    "validate-official-cash-events-v321",
    "compare-cash-amount-candidates-v321",
    "prepare-benchmark-etf-distributions-v321",
    "validate-benchmark-etf-distributions-v321",
    "inject-benchmark-etf-events-v321",
    "summarize-stock-dividend-resolution-v321",
    "acquire-kodex-distributions-v321",
    "build-stock-dividend-ambiguity-report-v321",
    "discover-kodex-dynamic-endpoints-v321",
    "refine-stock-dividend-candidates-v321",
    "rank-probe-kodex-endpoints-v321",
    "acquire-stock-dividend-decisions-v321",
    "build-stock-dividend-exdate-queue-v321",
    "inspect-kodex-high-signal-responses-v321",
    "extract-dart-dividend-record-dates-v321",
    "merge-dividend-date-candidates-v321",
    "build-explicit-stock-exdate-evidence-v321",
    "export-benchmark-calendar-v321",
    "build-record-date-calendar-candidates-v321",
    "parse-kodex-distribution-tables-v321",
    "build-market-exdate-verification-queue-v321",
    "validate-official-market-exdates-v321",
    "summarize-kodex-high-signal-bodies-v321",
})


def run_dividend_command(
    conn: sqlite3.Connection,
    settings,
    args,
) -> None:
    """Run guarded stock-dividend, ETF, and KODEX evidence commands."""
    if args.command not in DIVIDEND_COMMANDS:
        raise ValueError(f"지원하지 않는 배당 검증 명령입니다: {args.command}")

    if args.command == "build-stock-cash-amount-candidates-v321":
        try:
            result = build_stock_cash_amount_candidates_v321(
                dividend_facts_csv=args.dividend_facts_csv,
                verification_csv=args.verification_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                etf_codes=args.etf_code,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.8] {exc}")
        print("[V3.2.1 Phase 5.8 Stock Cash Amount Candidates]")
        print(f"배당 queue: {result['queue_rows']:,}")
        print(f"유일 금액 candidate: {result['amount_candidate_rows']:,}")
        print(f"금액 미해결: {result['unresolved_amount_rows']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
        print("주의: DART 금액 후보만으로는 ex-date가 없어 strict evidence가 아닙니다.")
    elif args.command == "prepare-official-cash-events-v321":
        try:
            result = prepare_official_cash_event_template_v321(
                verification_csv=args.verification_csv,
                output_csv=args.output_csv,
                etf_codes=args.etf_code,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.8] {exc}")
        print("[V3.2.1 Phase 5.8 Official Cash Event Template]")
        print(f"전체: {result['rows']:,} / STOCK: {result['stock_rows']:,} / ETF: {result['etf_rows']:,}")
        print(f"Output: {result['output_csv']}")
        print("실제 공식 ex/effective-date, known_at, cash_amount, source를 채우기 전에는 검증하지 마세요.")
    elif args.command == "validate-official-cash-events-v321":
        try:
            result = validate_official_cash_events_v321(
                official_cash_events_csv=args.official_cash_events_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.8] {exc}")
        print("[V3.2.1 Phase 5.8 Strict Cash Evidence]")
        print(f"Strict cash evidence: {result['strict_cash_evidence_rows']:,}")
        print(f"Stock dividends: {result['stock_dividend_rows']:,}")
        print(f"ETF distributions: {result['etf_distribution_rows']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "compare-cash-amount-candidates-v321":
        try:
            result = compare_cash_amount_candidates_v321(
                strict_cash_evidence_csv=args.strict_cash_evidence_csv,
                amount_candidates_csv=args.amount_candidates_csv,
                output_csv=args.output_csv,
                tolerance=args.tolerance,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.8] {exc}")
        print("[V3.2.1 Phase 5.8 Cash Amount Cross-check]")
        print(f"Rows: {result['rows']:,} / MATCH: {result['matches']:,} / MISMATCH: {result['mismatches']:,}")
        print(f"Audit: {result['output_csv']}")
    elif args.command == "prepare-benchmark-etf-distributions-v321":
        result = prepare_benchmark_etf_distribution_template_v321(
            output_csv=args.output_csv, code=args.code,
        )
        print("[V3.2.1 Phase 5.9 Benchmark ETF Distribution Template]")
        print(f"Output: {result['output_csv']}")
        print(f"Manifest: {result['manifest']}")
        print("실제 삼성자산운용/KRX 분배금 이력을 입력하기 전에는 strict 검증하지 마세요.")
    elif args.command == "validate-benchmark-etf-distributions-v321":
        try:
            result = validate_benchmark_etf_distributions_v321(
                official_csv=args.official_csv,
                strict_evidence_csv=args.strict_evidence_csv,
                audit_csv=args.audit_csv,
                code=args.code,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.9] {exc}")
        print("[V3.2.1 Phase 5.9 Benchmark ETF Strict Distribution Evidence]")
        print(f"Strict rows: {result['strict_rows']:,}")
        print(f"Ex-date range: {result['first_ex_date']} ~ {result['last_ex_date']}")
        print(f"Evidence: {result['strict_evidence_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "inject-benchmark-etf-events-v321":
        try:
            result = inject_benchmark_etf_events_v321(
                strict_evidence_csv=args.strict_evidence_csv,
                verification_csv=args.verification_csv,
                queue_registry_csv=args.queue_registry_csv,
                output_verification_csv=args.output_verification_csv,
                output_registry_csv=args.output_registry_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.9] {exc}")
        print("[V3.2.1 Phase 5.9 Benchmark ETF Queue Injection]")
        print(f"ETF events added: {result['etf_rows_added']:,}")
        print(f"Verification rows: {result['original_verification_rows']:,} -> {result['combined_verification_rows']:,}")
        print(f"Verification: {result['output_verification_csv']}")
        print(f"Registry: {result['output_registry_csv']}")
    elif args.command == "summarize-stock-dividend-resolution-v321":
        try:
            result = summarize_stock_dividend_resolution_v321(
                amount_candidates_csv=args.amount_candidates_csv,
                amount_audit_csv=args.amount_audit_csv,
                output_json=args.output_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.9] {exc}")
        print("[V3.2.1 Phase 5.9 Stock Dividend Resolution Summary]")
        print(f"Cash amount candidates: {result['cash_amount_candidate_rows']:,}")
        print(f"Queue audited: {result['queue_rows_audited']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_json']}")
    elif args.command == "acquire-kodex-distributions-v321":
        try:
            result = acquire_kodex_distribution_candidates_v321(
                output_dir=args.output_dir,
                url=args.url,
                timeout_seconds=args.timeout_seconds,
            )
        except Exception as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.10] {type(exc).__name__}: {exc}")
        print("[V3.2.1 Phase 5.10 KODEX 069500 Distribution Acquisition]")
        print(f"Candidate rows: {result['candidate_rows']:,}")
        print(f"Candidates: {result['outputs']['candidates']}")
        print(f"Raw HTML: {result['outputs']['raw_html']}")
        print(f"Manifest: {result['manifest_path']}")
        print("정책 문구는 이벤트로 만들지 않았습니다. 실제 날짜+금액 행만 candidate입니다.")
    elif args.command == "build-stock-dividend-ambiguity-report-v321":
        try:
            result = build_stock_dividend_ambiguity_report_v321(
                amount_audit_csv=args.amount_audit_csv,
                amount_candidates_csv=args.amount_candidates_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.10] {exc}")
        print("[V3.2.1 Phase 5.10 Stock Dividend Ambiguity Report]")
        print(f"Rows: {result['rows']:,}")
        print(f"Unique/Ambiguous/Missing: {result['unique']}/{result['ambiguous']}/{result['missing']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "discover-kodex-dynamic-endpoints-v321":
        try:
            result = discover_kodex_dynamic_endpoints_v321(
                product_url=args.product_url,
                output_dir=args.output_dir,
                timeout_seconds=args.timeout_seconds,
                max_scripts=args.max_scripts,
            )
        except Exception as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.11] {type(exc).__name__}: {exc}")
        print("[V3.2.1 Phase 5.11 KODEX Dynamic Endpoint Discovery]")
        print(f"Scripts discovered/scanned: {result['scripts_discovered']}/{result['scripts_scanned']}")
        print(f"Endpoint candidates: {result['endpoint_candidates']}")
        print(f"Candidates: {result['outputs']['endpoint_candidates']}")
        print(f"Script audit: {result['outputs']['script_audit']}")
        print(f"Manifest: {result['manifest_path']}")
        print("주의: endpoint 후보는 아직 이벤트 evidence가 아닙니다.")
    elif args.command == "refine-stock-dividend-candidates-v321":
        try:
            result = refine_stock_dividend_candidates_v321(
                dividend_facts_csv=args.dividend_facts_csv,
                verification_csv=args.verification_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                etf_codes=args.etf_code,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.11] {exc}")
        print("[V3.2.1 Phase 5.11 Refined Stock Dividend Candidates]")
        print(f"Queue rows: {result['queue_rows']:,}")
        print(f"Amount candidates: {result['candidate_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "rank-probe-kodex-endpoints-v321":
        try:
            result = rank_and_probe_kodex_endpoints_v321(
                candidate_csv=args.candidate_csv,
                output_csv=args.output_csv,
                top_n=args.top_n,
                timeout_seconds=args.timeout_seconds,
                product_host=args.product_host,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.12] {exc}")
        print("[V3.2.1 Phase 5.12 KODEX Endpoint Rank/Probe]")
        print(f"Input candidates: {result['input_candidates']:,}")
        print(f"Probed: {result['probed']:,} / successful: {result['successful']:,}")
        print(f"High response score: {result['high_response_score']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Manifest: {result['manifest']}")
        print("주의: probe 결과도 아직 분배금 이벤트 evidence가 아닙니다.")
    elif args.command == "acquire-stock-dividend-decisions-v321":
        try:
            client = DartClient(settings.dart_api_key)
            result = acquire_stock_dividend_decision_disclosures_v321(
                client,
                universe_csv=args.universe_csv,
                start=args.start,
                end=args.end,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                sleep_seconds=args.sleep_seconds,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.12] {exc}")
        print("[V3.2.1 Phase 5.12 Stock Dividend Decision Disclosures]")
        print(f"Codes: {result['codes']:,}")
        print(f"Decision rows: {result['decision_rows']:,}")
        print(f"Failed codes: {result['failed_codes']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "build-stock-dividend-exdate-queue-v321":
        try:
            result = build_stock_dividend_exdate_resolution_queue_v321(
                refined_amount_candidates_csv=args.refined_amount_candidates_csv,
                dividend_decisions_csv=args.dividend_decisions_csv,
                output_csv=args.output_csv,
                match_days=args.match_days,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.12] {exc}")
        print("[V3.2.1 Phase 5.12 Stock Dividend Ex-date Resolution Queue]")
        print(f"Rows: {result['rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print("effective_date는 공식 ex-date/record-date 매핑 전까지 비워 둡니다.")
    elif args.command == "inspect-kodex-high-signal-responses-v321":
        try:
            result = inspect_kodex_probe_responses_v321(
                probe_csv=args.probe_csv,
                output_dir=args.output_dir,
                min_response_keyword_score=args.min_response_keyword_score,
                timeout_seconds=args.timeout_seconds,
                product_host=args.product_host,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.13] {exc}")
        print("[V3.2.1 Phase 5.13 KODEX High-signal Response Inspection]")
        print(f"Selected endpoints: {result['selected_endpoints']:,}")
        print(f"Successful responses: {result['successful_responses']:,}")
        print(f"Responses with date fields: {result['responses_with_date_fields']:,}")
        print(f"Responses with amount fields: {result['responses_with_amount_fields']:,}")
        print(f"Field candidates: {result['field_candidates']:,}")
        print(f"Audit: {result['audit_csv']}")
        print(f"Fields: {result['fields_csv']}")
        print(f"Manifest: {result['manifest']}")
        print("주의: 날짜/금액 field 후보도 아직 ETF 분배금 strict evidence가 아닙니다.")
    elif args.command == "extract-dart-dividend-record-dates-v321":
        try:
            client = DartClient(settings.dart_api_key)
            result = extract_dart_dividend_record_dates_v321(
                client,
                decision_disclosures_csv=args.decision_disclosures_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                sleep_seconds=args.sleep_seconds,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.13] {exc}")
        print("[V3.2.1 Phase 5.13 DART Dividend Official Date Extraction]")
        print(f"Disclosures: {result['disclosures']:,}")
        print(f"Date candidates: {result['date_candidates']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
        print("RECORD_DATE는 아직 ex-date가 아닙니다.")
    elif args.command == "merge-dividend-date-candidates-v321":
        try:
            result = merge_dividend_amount_and_record_candidates_v321(
                exdate_queue_csv=args.exdate_queue_csv,
                dart_record_candidates_csv=args.dart_record_candidates_csv,
                output_csv=args.output_csv,
                match_days=args.match_days,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.13] {exc}")
        print("[V3.2.1 Phase 5.13 Dividend Amount + Official Date Merge]")
        print(f"Rows: {result['rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print("effective_date는 EX_DATE 확정 또는 거래일 캘린더 변환 전까지 비워 둡니다.")
    elif args.command == "build-explicit-stock-exdate-evidence-v321":
        try:
            result = build_explicit_stock_exdate_strict_evidence_v321(
                stock_dividend_date_resolution_csv=args.stock_dividend_date_resolution_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.14] {exc}")
        print("[V3.2.1 Phase 5.14 Explicit Stock Ex-date Strict Evidence]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Strict rows: {result['strict_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "export-benchmark-calendar-v321":
        try:
            result = export_benchmark_calendar_from_db_v321(
                conn,
                code=args.benchmark_code,
                output_csv=args.output_csv,
                include_post_cutoff=args.include_post_cutoff,
            )
        except ValueError as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.14] {exc}")
        print("[V3.2.1 Phase 5.14 Benchmark Trading Calendar Export]")
        print(f"Code: {result['code']} / rows: {result['rows']:,}")
        print(f"Range: {result['first_date']} ~ {result['last_date']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "build-record-date-calendar-candidates-v321":
        try:
            result = build_record_date_calendar_candidates_v321(
                stock_dividend_date_resolution_csv=args.stock_dividend_date_resolution_csv,
                benchmark_prices_csv=args.benchmark_prices_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.14] {exc}")
        print("[V3.2.1 Phase 5.14 Record-date Calendar Context]")
        print(f"Rows: {result['rows']:,}")
        print(f"Output: {result['output_csv']}")
        print("주의: prior trading day 후보는 strict ex-date evidence가 아닙니다.")
    elif args.command == "parse-kodex-distribution-tables-v321":
        try:
            result = parse_kodex_distribution_tables_v321(
                bodies_dir=args.bodies_dir,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.14] {exc}")
        print("[V3.2.1 Phase 5.14 KODEX Distribution Table Parser]")
        print(f"Body files: {result['body_files']:,}")
        print(f"Candidate pairs: {result['candidate_pairs']:,}")
        print(f"Files with pairs: {result['files_with_pairs']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "build-market-exdate-verification-queue-v321":
        try:
            result = build_market_exdate_verification_queue_v321(
                stock_dividend_date_resolution_csv=args.stock_dividend_date_resolution_csv,
                record_date_calendar_candidates_csv=args.record_date_calendar_candidates_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.15] {exc}")
        print("[V3.2.1 Phase 5.15 Market Ex-date Verification Queue]")
        print(f"Rows: {result['rows']:,}")
        print(f"Priority counts: {result['priority_counts']}")
        print(f"Output: {result['output_csv']}")
        print("calendar prior-day는 참고값이며 market_ex_date를 자동 채우지 않습니다.")
    elif args.command == "validate-official-market-exdates-v321":
        try:
            result = validate_official_market_exdates_v321(
                verification_csv=args.verification_csv,
                strict_evidence_csv=args.strict_evidence_csv,
                audit_csv=args.audit_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.15] {exc}")
        print("[V3.2.1 Phase 5.15 Official Market Ex-date Strict Evidence]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Strict rows: {result['strict_rows']:,}")
        print(f"Invalid rows: {result['invalid_rows']:,}")
        print(f"Evidence: {result['strict_evidence_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "summarize-kodex-high-signal-bodies-v321":
        try:
            result = summarize_kodex_high_signal_bodies_v321(
                response_audit_csv=args.response_audit_csv,
                field_candidates_csv=args.field_candidates_csv,
                output_json=args.output_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.15] {exc}")
        print("[V3.2.1 Phase 5.15 KODEX High-signal Summary]")
        print(f"Responses: {result['responses']:,}")
        print(f"Date-field responses: {result['responses_with_date_fields']:,}")
        print(f"Amount-field responses: {result['responses_with_amount_fields']:,}")
        print(f"Field candidate rows: {result['field_candidate_rows']:,}")
        print(f"Output: {result['output_json']}")
