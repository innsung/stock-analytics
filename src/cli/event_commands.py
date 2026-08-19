from __future__ import annotations

import sqlite3

from src.dart.client import DartClient
from src.ml.event_reconciliation_v321 import (
    finalize_event_reconciliation_v321,
    prepare_event_verification_v321,
)
from src.ml.market_effective_date_v321 import (
    PykrxMarketAdjustmentProvider,
    build_market_adjustment_evidence_v321,
    merge_strict_evidence_v321,
)
from src.ml.official_event_acquisition_v321 import (
    acquire_official_event_candidates_v321,
    enrich_official_evidence_template_v321,
)
from src.ml.official_event_resolver_v321 import (
    prepare_official_event_evidence_template_v321,
    resolve_official_events_v321,
)
from src.ml.payout_action_acquisition_v321 import (
    acquire_payout_action_facts_v321,
    build_event_reconciliation_template_v321,
)
from src.ml.total_return_v321 import build_total_return_history_v321


EVENT_COMMANDS = frozenset({
    "acquire-payout-actions-v321",
    "build-event-reconciliation-v321",
    "build-total-return-v321",
    "prepare-event-verification-v321",
    "finalize-event-reconciliation-v321",
    "prepare-official-event-evidence-v321",
    "resolve-official-events-v321",
    "acquire-official-event-candidates-v321",
    "enrich-official-evidence-v321",
    "build-market-adjustment-evidence-v321",
    "merge-strict-evidence-v321",
})


def run_event_command(
    conn: sqlite3.Connection,
    settings,
    args,
    *,
    load_universe,
) -> None:
    """Run guarded payout and corporate-action evidence commands."""
    if args.command not in EVENT_COMMANDS:
        raise ValueError(f"지원하지 않는 이벤트 명령입니다: {args.command}")

    if args.command == "acquire-payout-actions-v321":
        try:
            codes, _ = load_universe(args.universe_csv)
            if not codes:
                raise ValueError("유니버스 CSV에 활성 종목이 없습니다.")
            client = DartClient(settings.dart_api_key)
            result = acquire_payout_action_facts_v321(
                client, codes=codes, start_year=args.start_year, end_year=args.end_year,
                output_dir=args.output_dir, max_retries=args.max_retries,
                retry_backoff_seconds=args.retry_backoff_seconds,
                sleep_seconds=args.sleep_seconds,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.3] {exc}")
        print("[V3.2.1 Phase 5.3 Payout/Action Acquisition]")
        print(f"상태: {result['status']}")
        print(f"배당 공시 fact: {result['dividend_fact_rows']:,}행")
        print(f"기업행사 공시 후보: {result['corporate_action_disclosure_rows']:,}행")
        print(f"실패/부분 연도 요청: {result['failed_year_requests']} / {result['partial_year_requests']}")
        print("Total Return 준비: NO (효력일/배당락일/지급일 검증 전 canonical 승격 금지)")
        print(f"Manifest: {result['manifest_path']}")
        print("다음 명령: python -m src.main build-event-reconciliation-v321 "
              f"--dividend-facts-csv {args.output_dir}/dividend_disclosure_facts.csv "
              f"--action-disclosures-csv {args.output_dir}/corporate_action_disclosures.csv "
              f"--output-csv {args.output_dir}/event_reconciliation_queue.csv")
    elif args.command == "build-event-reconciliation-v321":
        try:
            result = build_event_reconciliation_template_v321(
                dividend_facts_csv=args.dividend_facts_csv,
                action_disclosures_csv=args.action_disclosures_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.3] {exc}")
        print("[V3.2.1 Phase 5.3 Event Reconciliation]")
        print(f"검증 대기 이벤트: {result['rows']:,}행")
        print(f"출력: {result['output_csv']}")
        print("주의: 이 파일은 검증 큐이며 canonical corporate_actions.csv가 아닙니다.")
    elif args.command == "build-total-return-v321":
        try:
            result = build_total_return_history_v321(
                conn, corporate_actions_csv=args.corporate_actions_csv,
                coverage_json=args.coverage_json, output_csv=args.output_csv,
                benchmark_code=args.benchmark_code)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.54 Guarded Total Return] {exc}")
        print(f"[V3.2.1 Total Return Foundation] {result['status']}")
        print(f"저장: {result['rows']:,}행 / {result['codes']}종목")
        print(f"CSV: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
        print(f"Manifest: {result['manifest_json']}")
    elif args.command == "prepare-event-verification-v321":
        try:
            result = prepare_event_verification_v321(
                queue_csv=args.queue_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.4] {exc}")
        print("[V3.2.1 Phase 5.4 Verification Template]")
        print(f"검증 대상: {result['rows']:,}행")
        print(f"Verification CSV: {result['output_csv']}")
        print(f"Queue registry: {result['queue_registry']}")
        print("주의: resolution_status=VERIFIED에는 실제 효력일/known_at/source가 필요합니다.")
        print("한 queue_event_id에 여러 실제 배당 이벤트가 있으면 행을 복제해 각각 VERIFIED로 기록할 수 있습니다.")
    elif args.command == "finalize-event-reconciliation-v321":
        try:
            result = finalize_event_reconciliation_v321(
                verification_csv=args.verification_csv,
                queue_registry_csv=args.queue_registry_csv,
                canonical_output_csv=args.canonical_output_csv,
                audit_output_csv=args.audit_output_csv,
                coverage_json=args.coverage_json,
                coverage_start=args.coverage_start,
                coverage_end=args.coverage_end,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.4] {exc}")
        print("[V3.2.1 Phase 5.4 Canonicalization]")
        print(f"Canonical verified events: {result['canonical_rows']:,}행")
        print(f"Unresolved queue events: {result['unresolved_queue_events']:,}행")
        print(f"Cash distributions complete: {result['cash_distributions_complete']}")
        print(f"Capital actions complete: {result['capital_actions_complete']}")
        print(f"Coverage complete: {result['coverage_complete']}")
        print(f"Canonical: {result['canonical_output_csv']}")
        print(f"Audit: {result['audit_output_csv']}")
        print(f"Coverage: {result['coverage_json']}")
        if not result["coverage_complete"]:
            print("Total Return 생성 금지: unresolved event가 남아 있습니다.")
        else:
            print("다음 단계: build-total-return-v321로 canonical Total Return 생성 가능")
    elif args.command == "prepare-official-event-evidence-v321":
        try:
            result = prepare_official_event_evidence_template_v321(
                verification_csv=args.verification_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.5] {exc}")
        print("[V3.2.1 Phase 5.5 Official Evidence Template]")
        print(f"대상 이벤트: {result['rows']:,}행")
        print(f"Evidence CSV: {result['output_csv']}")
        print("주의: 실제 공식 effective/ex-date, known_at, 금액/조정계수, source가 없는 행은 VERIFIED 근거가 될 수 없습니다.")
    elif args.command == "resolve-official-events-v321":
        try:
            result = resolve_official_events_v321(
                verification_csv=args.verification_csv,
                evidence_csv=args.evidence_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                not_applicable_csv=args.not_applicable_csv,
                date_window_days=args.date_window_days,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.5] {exc}")
        print("[V3.2.1 Phase 5.5 Official Event Resolver]")
        print(f"Queue events: {result['queue_events']:,}")
        print(f"VERIFIED: {result['verified_queue_events']:,}")
        print(f"NOT_APPLICABLE: {result['not_applicable_queue_events']:,}")
        print(f"UNRESOLVED: {result['unresolved_queue_events']:,}")
        print(f"Resolved verification: {result['verification_output_csv']}")
        print(f"Audit: {result['audit_csv']}")
        print(f"Manifest: {result['manifest']}")
        if result["unresolved_queue_events"]:
            print("Canonicalization/Total Return 차단 유지: UNRESOLVED 이벤트가 남아 있습니다.")
        else:
            print("다음 단계: finalize-event-reconciliation-v321 실행 가능")
    elif args.command == "acquire-official-event-candidates-v321":
        try:
            client = DartClient(settings.dart_api_key)
            result = acquire_official_event_candidates_v321(
                client,
                universe_csv=args.universe_csv,
                start=args.start,
                end=args.end,
                output_dir=args.output_dir,
                max_retries=args.max_retries,
                retry_backoff_seconds=args.retry_backoff_seconds,
                sleep_seconds=args.sleep_seconds,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.6] {exc}")
        print("[V3.2.1 Phase 5.6 Official Event Candidate Acquisition]")
        print(f"상태: {result['status']}")
        print(f"공식 상세 candidate: {result['candidate_rows']:,}행")
        print(f"실패 endpoint 요청: {result['failed_endpoint_requests']:,}")
        print(f"Manifest: {result['manifest_path']}")
        print("주의: candidate는 strict evidence가 아니며 Total Return에 바로 사용할 수 없습니다.")
    elif args.command == "enrich-official-evidence-v321":
        try:
            result = enrich_official_evidence_template_v321(
                evidence_template_csv=args.evidence_template_csv,
                candidate_csv=args.candidate_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.6] {exc}")
        print("[V3.2.1 Phase 5.6 Evidence Enrichment]")
        print(f"Evidence rows: {result['rows']:,}")
        print(f"공식 candidate가 연결된 행: {result['rows_with_candidates']:,}")
        print(f"출력: {result['output_csv']}")
        print("주의: enrichment는 검토 보조이며 빈 strict 필드를 자동 VERIFIED로 채우지 않습니다.")
    elif args.command == "build-market-adjustment-evidence-v321":
        try:
            provider = PykrxMarketAdjustmentProvider()
            result = build_market_adjustment_evidence_v321(
                provider,
                official_candidates_csv=args.official_candidates_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
                window_days=args.window_days,
                max_match_distance_days=args.max_match_distance_days,
                ratio_tolerance=args.ratio_tolerance,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.7] {exc}")
        print("[V3.2.1 Phase 5.7 KRX Market Adjustment Resolver]")
        print(f"Official candidates: {result['candidate_rows']:,}")
        print(f"Strict market evidence: {result['strict_market_evidence_rows']:,}")
        print(f"Unresolved candidates: {result['unresolved_candidate_rows']:,}")
        print(f"Evidence: {result['output_csv']}")
        print(f"Audit: {result['audit_csv']}")
        print(f"Manifest: {result['manifest']}")
        print("현금배당/ETF 분배금은 가격갭만으로 자동 VERIFIED하지 않습니다.")
    elif args.command == "merge-strict-evidence-v321":
        try:
            result = merge_strict_evidence_v321(
                evidence_csvs=args.evidence_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.7] {exc}")
        print("[V3.2.1 Phase 5.7 Strict Evidence Merge]")
        print(f"Merged evidence: {result['rows']:,}행")
        print(f"Output: {result['output_csv']}")
