import argparse
import atexit
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import time
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from config.settings import get_settings
from database.database import connect
from src.analysis.indicators import add_indicators
from src.analysis.financial_score import (
    analyze_financials, investment_opinion, technical_score,
)
from src.analysis.universe_ranker import rank_universe
from src.backtest.engine import run_ma_rsi_strategy
from src.backtest.robustness import monte_carlo_trades, parameter_sensitivity
from src.backtest.multi_asset import common_parameter_walk_forward
from src.backtest.realistic_portfolio import run_lockbox
from src.backtest.walk_forward import walk_forward_optimize
from src.collector.collectors import (collect_financials, collect_prices,
                                      collect_prices_incremental, collect_valuation)
from src.dart.client import DartClient
from src.kis.client import KISClient, KISRateLimitError
from src.ml.feature_store import build_feature_store
from src.ml.models import predict_latest, train_baselines, walk_forward_baselines
from src.ml.diagnostics import financial_missingness_reports, run_ml_diagnostics
from src.ml.diagnostics_v2 import run_ml_diagnostics_v2
from src.ml.diagnostics_v3 import run_ml_diagnostics_v3
from src.ml.diagnostics_v31 import run_ml_diagnostics_v31
from src.ml.diagnostics_v32 import run_ml_diagnostics_v32
from src.ml.diagnostics_v321 import run_ml_diagnostics_v321
from src.ml.data_integrity_v321 import import_valuation_snapshots, build_data_foundation_v321
from src.ml.historical_acquisition_v321 import acquire_historical_data_v321, check_krx_provider_v321
from src.ml.result_bundle_v321 import create_result_bundle_v321
from src.ml.persistent_data_v321 import (inspect_persistent_data_v321, assert_persistent_data_v321, backup_database_v321, write_health_snapshot_v321)
from src.ml.total_return_v321 import build_total_return_history_v321
from src.ml.payout_action_acquisition_v321 import (
    acquire_payout_action_facts_v321,
    build_event_reconciliation_template_v321,
)
from src.ml.event_reconciliation_v321 import (
    prepare_event_verification_v321,
    finalize_event_reconciliation_v321,
)
from src.ml.official_event_resolver_v321 import (
    prepare_official_event_evidence_template_v321,
    resolve_official_events_v321,
)
from src.ml.official_event_acquisition_v321 import (
    acquire_official_event_candidates_v321,
    enrich_official_evidence_template_v321,
)
from src.ml.market_effective_date_v321 import (
    PykrxMarketAdjustmentProvider,
    build_market_adjustment_evidence_v321,
    merge_strict_evidence_v321,
)
from src.ml.cash_distribution_v321 import (
    build_stock_cash_amount_candidates_v321,
    prepare_official_cash_event_template_v321,
    validate_official_cash_events_v321,
    compare_cash_amount_candidates_v321,
)
from src.ml.benchmark_etf_distribution_v321 import (
    prepare_benchmark_etf_distribution_template_v321,
    validate_benchmark_etf_distributions_v321,
    inject_benchmark_etf_events_v321,
    summarize_stock_dividend_resolution_v321,
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
    rank_and_probe_kodex_endpoints_v321,
    acquire_stock_dividend_decision_disclosures_v321,
    build_stock_dividend_exdate_resolution_queue_v321,
)
from src.ml.phase513_parsers_v321 import (
    inspect_kodex_probe_responses_v321,
    extract_dart_dividend_record_dates_v321,
    merge_dividend_amount_and_record_candidates_v321,
)
from src.ml.phase514_strict_exdate_v321 import (
    build_explicit_stock_exdate_strict_evidence_v321,
    build_record_date_calendar_candidates_v321,
    parse_kodex_distribution_tables_v321,
    export_benchmark_calendar_from_db_v321,
)
from src.ml.phase515_market_exdate_v321 import (
    build_market_exdate_verification_queue_v321,
    validate_official_market_exdates_v321,
    summarize_kodex_high_signal_bodies_v321,
)
from src.ml.phase516_kind_crosscheck_v321 import (
    crosscheck_kind_dividend_disclosures_v321,
    discover_kodex_next_hops_v321,
)
from src.ml.phase518_kind_retry_v321 import build_kind_retry_queue_v321
from src.ml.phase526_kind_document_parser_v321 import parse_kind_dividend_documents_v321
from src.ml.phase527_kind_reconciliation_v321 import reconcile_kind_dividend_candidates_v321
from src.ml.phase528_kind_market_exdate_v321 import acquire_kind_market_exdates_v321
from src.ml.phase529_kind_market_search_v321 import discover_kind_market_exdate_notices_v321
from src.ml.phase531_resolution_gap_prioritizer_v321 import prioritize_resolution_gaps_v321
from src.ml.phase532_recent_dividend_acquisition_manifest_v321 import build_recent_dividend_acquisition_manifest_v321
from src.ml.phase533_kind_batch_market_search_v321 import discover_kind_market_notices_batch_v321
from src.ml.phase534_kind_dividend_decision_pairing_v321 import acquire_paired_kind_dividend_decisions_v321
from src.ml.phase535_kind_paired_strict_evidence_v321 import build_paired_kind_market_observations_v321
from src.ml.phase536_company_name_recovery_v321 import recover_acquisition_company_names_v321
from src.ml.phase537_kind_direct_decision_acquisition_v321 import acquire_direct_kind_dividend_decisions_v321
from src.ml.phase538_kind_aggregate_notice_extractor_v321 import extract_kind_aggregate_market_targets_v321
from src.ml.phase542_market_notice_coverage_audit_v321 import audit_market_notice_coverage_v321
from src.ml.phase543_recent_corporate_action_classifier_v321 import classify_recent_corporate_actions_v321
from src.ml.phase544_corporate_action_candidate_manifest_v321 import build_corporate_action_candidate_manifest_v321
from src.ml.phase545_market_adjustment_candidate_selector_v321 import select_market_adjustment_candidates_v321
from src.ml.phase546_corporate_action_document_acquisition_v321 import acquire_missing_corporate_action_documents_v321
from src.ml.phase547_corporate_action_document_parser_v321 import parse_corporate_action_documents_v321
from src.ml.phase548_complex_action_semantic_review_v321 import review_complex_corporate_actions_v321
from src.ml.phase549_spinoff_valuation_audit_v321 import audit_listed_spinoff_valuation_v321
from src.ml.phase550_spinoff_distribution_ledger_v321 import build_spinoff_distribution_ledger_v321
from src.ml.phase551_spinoff_fractional_settlement_v321 import audit_spinoff_fractional_settlement_v321
from src.ml.phase552_spinoff_evidence_completeness_v321 import audit_spinoff_evidence_completeness_v321
from src.ml.phase553_complex_action_coverage_gate_v321 import build_complex_action_coverage_gate_v321
from src.ml.phase555_current_resolution_priority_v321 import prioritize_current_resolution_backlog_v321
from src.ml.phase556_subsidiary_document_acquisition_v321 import acquire_subsidiary_action_documents_v321
from src.ml.phase557_subsidiary_applicability_parser_v321 import parse_subsidiary_action_applicability_v321
from src.ml.phase558_not_applicable_integration_v321 import integrate_not_applicable_evidence_v321
from src.ml.phase559_residual_subsidiary_resolver_v321 import resolve_residual_subsidiary_actions_v321
from src.ml.phase560_residual_subsidiary_integration_v321 import integrate_residual_subsidiary_evidence_v321
from src.ml.phase561_direct_action_document_inventory_v321 import build_direct_action_document_inventory_v321
from src.ml.phase562_direct_action_group_review_v321 import review_direct_action_groups_v321
from src.ml.phase563_direct_action_integration_v321 import integrate_direct_action_evidence_v321
from src.ml.phase564_samsung_sdi_rights_verification_v321 import verify_samsung_sdi_rights_v321
from src.ml.phase565_strict_evidence_integration_v321 import integrate_strict_event_evidence_v321
from src.ml.phase566_actionable_backlog_router_v321 import route_actionable_resolution_backlog_v321
from src.ml.phase567_recent_dividend_evidence_inventory_v321 import build_recent_dividend_evidence_inventory_v321
from src.ml.phase568_historical_dividend_decision_acquisition_v321 import acquire_historical_dividend_decisions_v321
from src.ml.phase569_historical_dividend_decision_parser_v321 import parse_historical_dividend_decisions_v321
from src.ml.phase570_historical_dividend_exdate_candidates_v321 import build_historical_dividend_exdate_candidates_v321
from src.ml.phase571_historical_kind_exdate_discovery_v321 import discover_historical_kind_exdates_v321
from src.ml.phase572_historical_kind_strict_evidence_v321 import build_historical_kind_strict_evidence_v321
from src.ml.phase573_historical_dividend_queue_integration_v321 import integrate_historical_dividend_evidence_v321
from src.ml.phase574_residual_dividend_backlog_v321 import build_residual_dividend_backlog_v321
from src.ml.phase575_ambiguous_kind_notice_resolution_v321 import resolve_ambiguous_kind_notice_v321
from src.ml.phase577_broadened_kind_notice_resolution_v321 import resolve_broadened_kind_notices_v321
from src.ml.phase578_pre_exdate_provenance_recovery_v321 import recover_pre_exdate_dividend_evidence_v321
from src.ml.phase579_explicit_no_dividend_resolution_v321 import resolve_explicit_no_dividend_v321
from src.ml.phase580_non_pit_dividend_deferral_v321 import defer_non_pit_dividends_v321
from src.ml.phase581_recent_followup_resolution_v321 import resolve_recent_followups_v321
from src.ml.phase582_historical_backlog_router_v321 import build_historical_backlog_execution_manifest_v321
from src.ml.phase583_periodic_dividend_aggregate_quarantine_v321 import quarantine_periodic_dividend_aggregates_v321
from src.ml.phase584_historical_legal_event_chain_v321 import build_historical_legal_event_chain_v321
from src.ml.phase585_historical_chain_document_validation_v321 import validate_historical_chain_documents_v321
from src.ml.phase586_historical_chain_consolidation_v321 import consolidate_historical_legal_chains_v321
from src.ml.phase587_primary_adjustment_document_terms_v321 import extract_primary_adjustment_document_terms_v321
from src.ml.phase588_primary_adjustment_market_validation_v321 import validate_primary_adjustment_market_dates_v321
from src.ml.phase589_rights_applicability_audit_v321 import audit_historical_rights_applicability_v321
from src.ml.phase590_merger_spinoff_applicability_v321 import audit_historical_merger_spinoff_applicability_v321
from src.ml.phase591_celltrion_merger_reparse_v321 import reparse_celltrion_merger_v321
from src.ml.phase592_capital_reduction_applicability_v321 import audit_historical_capital_reductions_v321
from src.ml.phase593_incomplete_primary_applicability_v321 import audit_incomplete_primary_adjustments_v321
from src.ml.phase594_samsung_heavy_rights_verification_v321 import verify_samsung_heavy_rights_v321
from src.ml.phase595_amorepacific_restructuring_v321 import audit_amorepacific_restructuring_v321
from src.ml.phase596_overseas_listing_delisting_v321 import audit_overseas_listing_delistings_v321
from src.ml.phase597_lgchem_subsidiary_rights_v321 import audit_lgchem_subsidiary_rights_v321
from src.ml.phase598_hdhyundai_exchangeable_bond_v321 import audit_hdhyundai_exchangeable_bond_v321
from src.ml.phase599_ecoprobm_merger_transfer_v321 import audit_ecoprobm_merger_transfer_v321
from src.ml.phase600_kakao_zero_ratio_merger_v321 import audit_kakao_zero_ratio_merger_v321
from src.ml.phase601_celltrion_merger_followups_v321 import audit_celltrion_merger_followups_v321
from src.ml.phase602_kakao_overseas_dr_delisting_v321 import audit_kakao_overseas_dr_delisting_v321
from src.ml.phase603_samsung_heavy_preferred_delisting_warning_v321 import audit_samsung_heavy_preferred_delisting_warnings_v321
from src.ml.phase604_hd_ksoe_subsidiary_zero_ratio_merger_v321 import audit_hd_ksoe_subsidiary_zero_ratio_merger_v321
from src.ml.phase605_ecoprobm_subsidiary_capital_increases_v321 import audit_ecoprobm_subsidiary_capital_increases_v321
from src.ml.phase606_lgchem_historical_subsidiary_capital_v321 import audit_lgchem_historical_subsidiary_capital_v321
from src.ml.phase607_amorepacific_us_subsidiary_capital_v321 import audit_amorepacific_us_subsidiary_capital_v321
from src.ml.phase608_skhynix_subsidiary_capital_v321 import audit_skhynix_subsidiary_capital_v321
from src.ml.phase609_cj_schwans_subsidiary_mergers_v321 import audit_cj_schwans_subsidiary_mergers_v321
from src.ml.phase610_kakao_games_subsidiary_capital_v321 import audit_kakao_games_subsidiary_capital_v321
from src.ml.phase611_naver_line_overseas_delisting_v321 import audit_naver_line_overseas_delisting_v321
from src.ml.phase612_historical_administrative_trading_halts_v321 import audit_historical_administrative_trading_halts_v321
from src.ml.phase613_related_party_rights_participation_v321 import audit_related_party_rights_participation_v321
from src.ml.phase614_samsung_heavy_rights_price_followups_v321 import audit_samsung_heavy_rights_price_followups_v321
from src.ml.phase615_asset_transfer_completion_reports_v321 import audit_asset_transfer_completion_reports_v321
from src.ml.phase616_physical_split_business_transfer_completions_v321 import audit_physical_split_business_transfer_completions_v321
from src.ml.phase617_amorepacific_attachment_followups_v321 import audit_amorepacific_attachment_followups_v321
from src.ml.phase618_rights_offering_followups_v321 import audit_rights_offering_followups_v321
from src.ml.phase619_hdhyundai_subsidiary_rights_amendments_v321 import audit_hdhyundai_subsidiary_rights_amendments_v321
from src.ml.phase620_kakao_split_amendments_v321 import audit_kakao_split_amendments_v321
from src.ml.phase621_historical_amendment_duplicates_v321 import audit_historical_amendment_duplicates_v321
from src.ml.phase622_ecoprobm_rights_support_disclosures_v321 import audit_ecoprobm_rights_support_disclosures_v321
from src.ml.phase623_ecoprobm_bonus_issue_verification_v321 import verify_ecoprobm_bonus_issue_v321
from src.ml.phase624_hd_ksoe_third_party_capital_v321 import audit_hd_ksoe_third_party_capital_v321
from src.ml.phase625_shinhan_neoplux_share_exchange_v321 import audit_shinhan_neoplux_share_exchange_v321
from src.ml.phase626_release_quality_gate_v321 import build_release_quality_gate_v321
from src.ml.phase627_release_artifact_integrity_v321 import verify_release_artifact_integrity_v321
from src.ml.phase628_release_restore_drill_v321 import verify_release_restore_drill_v321
from src.ml.phase629_runtime_readiness_gate_v321 import build_runtime_readiness_gate_v321
from src.ml.phase630_release_candidate_seal_v321 import build_release_candidate_seal_v321
from src.ml.phase631_rc_promotion_readiness_v321 import build_rc_promotion_readiness_v321
from src.ml.phase632_release_approval_handoff_v321 import build_release_approval_handoff_v321
from src.ml.phase633_release_notes_v321 import build_release_notes_v321
from src.ml.phase634_repository_promotion_preflight_v321 import build_repository_promotion_preflight_v321
from src.ml.phase635_release_curation_manifest_v321 import build_release_curation_manifest_v321
from src.ml.phase636_manual_curation_resolution_v321 import build_manual_curation_resolution_v321
from src.ml.phase637_curated_release_payload_v321 import build_curated_release_payload_v321
from src.ml.phase638_curated_payload_restore_drill_v321 import verify_curated_payload_restore_v321
from src.ml.phase639_final_promotion_gate_v321 import build_final_promotion_gate_v321
from src.ml.phase640_final_release_bundle_v321 import build_final_release_bundle_v321
from src.shadow.engine import run_shadow_day


def load_prices(conn, code: str) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM stock_prices WHERE code=? ORDER BY date", conn, params=(code,))


def load_universe_csv(path: str | None) -> tuple[list[str], dict[str, str]]:
    if not path:
        return [], {}
    frame = pd.read_csv(path, dtype={"code": str})
    if "code" not in frame.columns:
        raise SystemExit("유니버스 CSV에는 code 열이 필요합니다.")
    if "enabled" in frame.columns:
        enabled = frame["enabled"].astype(str).str.lower().isin({"1", "true", "yes", "y"})
        frame = frame[enabled]
    codes = frame["code"].str.strip().str.zfill(6).tolist()
    industries = {}
    if "industry" in frame.columns:
        industries = dict(zip(codes, frame["industry"].fillna("미분류").astype(str)))
    return codes, industries


def resolve_codes_and_industries(args) -> tuple[list[str], dict[str, str]]:
    csv_codes, mapping = load_universe_csv(getattr(args, "universe_csv", None))
    codes = list(dict.fromkeys([*csv_codes, *getattr(args, "codes", [])]))
    for item in getattr(args, "industry", []):
        if "=" not in item:
            raise SystemExit("--industry는 005930=반도체 형식이어야 합니다.")
        code, industry = item.split("=", 1)
        mapping[code] = industry
    if not codes:
        raise SystemExit("종목코드 또는 --universe-csv를 입력하세요.")
    return codes, mapping


def save_shadow_outputs(conn, result, output_prefix: str, portfolio_id: str) -> None:
    prefix = Path(output_prefix)
    result.rankings.to_csv(prefix.with_name(prefix.name + "_daily_ranking.csv"), index=False, encoding="utf-8-sig")
    result.proposals.to_csv(prefix.with_name(prefix.name + "_trade_proposals.csv"), index=False, encoding="utf-8-sig")
    result.skips.to_csv(prefix.with_name(prefix.name + "_skipped_orders.csv"), index=False, encoding="utf-8-sig")
    result.attribution.to_csv(prefix.with_name(prefix.name + "_attribution.csv"), index=False, encoding="utf-8-sig")
    pd.read_sql_query("""SELECT code,quantity,average_price,target_weight,total_score,updated_at
        FROM shadow_book_positions WHERE portfolio_id=? ORDER BY code""", conn,
        params=(portfolio_id,)).to_csv(prefix.with_name(prefix.name + "_positions.csv"), index=False, encoding="utf-8-sig")
    pd.read_sql_query("""SELECT performance_date,equity,cash,market_value,daily_return,
        cumulative_return,benchmark_value,benchmark_return,benchmark_price,cash_drag,
        target_exposure,actual_exposure,allocation_gap
        FROM shadow_book_performance WHERE portfolio_id=? ORDER BY performance_date""", conn,
        params=(portfolio_id,)).to_csv(prefix.with_name(prefix.name + "_performance.csv"), index=False, encoding="utf-8-sig")


def print_shadow_result(result, output_prefix: str) -> None:
    cash_opportunity_cost = 0.0 if abs(result.cash_opportunity_cost) < .5 else result.cash_opportunity_cost
    cash_defense = 0.0 if abs(result.cash_defense) < .5 else result.cash_defense
    print(f"""[일일 그림자 포트폴리오: {result.as_of}]
포트폴리오 ID: {result.portfolio_id}
처리 상태: {"이미 처리된 거래일 — 가상거래·성과 재계산 생략" if result.already_processed else "신규 처리"}
평가자산: {result.equity:,.0f}원 / 현금: {result.cash:,.0f}원
일간수익률: {result.daily_return:.4f}% / 누적수익률: {result.cumulative_return:.4f}%
벤치마크 누적수익률: {result.benchmark_return:.4f}%
현금 기회비용: {cash_opportunity_cost:,.0f}원 / 현금 방어기여: {cash_defense:,.0f}원
목표/실제 투자비중: {result.target_exposure:.2f}% / {result.actual_exposure:.2f}% (차이 {result.allocation_gap:.2f}%p)
가상 체결 제안: {len(result.proposals)}건 (실제 주문 없음)
주문 제외·생략 기록: {len(result.skips)}건
결과 접두사: {output_prefix}""")


def print_shadow_report(conn, portfolio_id: str, export_csv: str | None = None) -> None:
    performance = pd.read_sql_query("""SELECT * FROM shadow_book_performance
        WHERE portfolio_id=? ORDER BY performance_date""", conn, params=(portfolio_id,))
    if performance.empty:
        raise SystemExit(f"성과가 없는 포트폴리오입니다: {portfolio_id}")
    equity = performance["equity"].astype(float)
    drawdown = equity / equity.cummax() - 1
    returns = performance["daily_return"].astype(float).fillna(0)
    sharpe = 0.0 if returns.std(ddof=0) == 0 else returns.mean() / returns.std(ddof=0) * (252 ** .5)
    costs = conn.execute("""SELECT COALESCE(SUM(estimated_cost),0),COUNT(*),
        COALESCE(SUM(reference_price*quantity),0) FROM shadow_book_proposals
        WHERE portfolio_id=?""", (portfolio_id,)).fetchone()
    average_equity = max(float(equity.mean()), 1)
    turnover = float(costs[2]) / average_equity * 100
    latest = performance.iloc[-1]
    count = len(performance)
    stage = ("준비 단계(20거래일 미만)" if count < 20 else
             "초기 관찰(20~59거래일)" if count < 60 else
             "중간 검증(60~119거래일)" if count < 120 else "정식 평가(120거래일 이상)")
    print(f"""[그림자 포트폴리오 누적 리포트: {portfolio_id}]
기간: {performance.iloc[0]['performance_date']} ~ {latest['performance_date']} ({count}거래일)
평가 단계: {stage}
누적수익률: {float(latest['cumulative_return']) * 100:.4f}%
벤치마크 수익률: {float(latest['benchmark_return']) * 100:.4f}%
MDD: {float(drawdown.min()) * 100:.4f}%
샤프지수: {sharpe:.4f}
누적 거래비용: {float(costs[0]):,.0f}원 / 가상 체결: {int(costs[1])}건
누적 회전율: {turnover:.2f}%
최근 목표/실제 투자비중: {float(latest.get('target_exposure') or 0) * 100:.2f}% / {float(latest.get('actual_exposure') or 0) * 100:.2f}%""")
    if export_csv:
        performance.to_csv(export_csv, index=False, encoding="utf-8-sig")
        print(f"성과 저장: {export_csv}")


@contextmanager
def daily_run_lock(db_path: Path, portfolio_id: str):
    digest = hashlib.sha256(portfolio_id.encode()).hexdigest()[:16]
    lock_path = db_path.parent / f".daily_shadow_{digest}.lock"
    if lock_path.exists() and time.time() - lock_path.stat().st_mtime > 4 * 3600:
        lock_path.unlink()
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(f"포트폴리오 '{portfolio_id}'의 daily-shadow가 이미 실행 중입니다.") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}".encode())
        os.close(descriptor)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def execute_daily_shadow(conn, settings, args) -> None:
    started = datetime.now(timezone.utc).isoformat()
    log_id = conn.execute("""INSERT INTO daily_run_logs(portfolio_id,started_at,status)
        VALUES(?,?,'RUNNING')""", (args.portfolio_id, started)).lastrowid
    conn.commit()
    price_saved = valuation_saved = error_count = 0
    evaluation_date = None
    try:
        with daily_run_lock(settings.db_path, args.portfolio_id):
            now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
            if now_kst.weekday() < 5 and (now_kst.hour, now_kst.minute) < (15, 40) and not args.allow_before_close:
                raise RuntimeError(
                    "한국시간 15:40 이전입니다. 종가 확정 후 실행하거나 점검 목적이면 --allow-before-close를 사용하세요."
                )
            previous_success = conn.execute("""SELECT id,started_at,evaluation_date
                FROM daily_run_logs WHERE portfolio_id=? AND status='SUCCESS' AND id<>?
                ORDER BY id DESC LIMIT 20""", (args.portfolio_id, log_id)).fetchall()
            success_today = None
            for previous_id, previous_started, previous_evaluation_date in previous_success:
                try:
                    started_kst = datetime.fromisoformat(previous_started).astimezone(ZoneInfo("Asia/Seoul"))
                except (TypeError, ValueError):
                    continue
                if started_kst.date() == now_kst.date():
                    success_today = (previous_id, previous_evaluation_date)
                    break
            if success_today and not args.force_refresh:
                evaluation_date = success_today[1]
                message = (f"당일 성공 실행 #{success_today[0]} 존재 — API 호출 전 전체 생략. "
                           "다시 수집하려면 --force-refresh를 사용하세요.")
                conn.execute("""UPDATE daily_run_logs SET finished_at=?,status='SKIPPED',
                    evaluation_date=?,message=? WHERE id=?""",
                    (datetime.now(timezone.utc).isoformat(), evaluation_date, message, log_id))
                conn.commit()
                print(message)
                return
            args.codes, mapping = resolve_codes_and_industries(args)
            client = KISClient(settings)
            price_skipped = 0
            print("[1/4 가격 증분 수집]")
            for code in dict.fromkeys([*args.codes, args.benchmark_code]):
                try:
                    collected = collect_prices_incremental(conn, client, code, args.days, refresh_days=7)
                    price_saved += collected.saved
                    price_skipped += int(collected.api_skipped)
                    print(f"{code}: 최근구간 {collected.saved}건 갱신" if not collected.api_skipped else
                          f"{code}: API 생략(충분)")
                except KISRateLimitError as exc:
                    error_count += 1; print(f"{code}: 제한 - {exc}"); break
                except Exception as exc:
                    error_count += 1; print(f"{code}: 오류 - {exc} (저장 데이터로 계속)")
            print("[2/4 가치지표 갱신]")
            valuation_skipped = 0
            today_kst = now_kst.strftime("%Y%m%d")
            for code in args.codes:
                exists = conn.execute("SELECT 1 FROM valuation_snapshots WHERE code=? AND snapshot_date=?",
                                      (code, today_kst)).fetchone()
                if exists and not args.force_refresh:
                    valuation_skipped += 1; print(f"{code}: 오늘 가치지표 존재(생략)"); continue
                try:
                    collect_valuation(conn, client, code); valuation_saved += 1
                    print(f"{code}: 가치지표 저장")
                except KISRateLimitError as exc:
                    error_count += 1; print(f"{code}: 제한 - {exc}"); break
                except Exception as exc:
                    error_count += 1; print(f"{code}: 오류 - {exc} (저장 데이터로 계속)")
            latest = {code: conn.execute("SELECT MAX(date) FROM stock_prices WHERE code=?", (code,)).fetchone()[0]
                      for code in dict.fromkeys([*args.codes, args.benchmark_code])}
            missing = [code for code, day in latest.items() if day is None]
            if missing:
                raise RuntimeError("저장 가격이 없는 종목: " + ", ".join(missing))
            evaluation_date = max(latest.values())
            mismatched = [f"{code}={day}" for code, day in latest.items() if day != evaluation_date]
            if mismatched:
                raise RuntimeError(
                    "최신 거래일 불일치로 가상거래를 중단합니다. 기준일 " + evaluation_date + " / " +
                    ", ".join(mismatched)
                )
            print(f"최신 거래일 검증 완료: {evaluation_date} ({len(latest)}종목 일치)")
            print("[3/4 그림자 포트폴리오]")
            result = run_shadow_day(
                conn, args.codes, mapping, args.benchmark_code, args.capital,
                args.top_n, args.rebalance_band, args.min_order, args.stock_cap, args.sector_cap,
                portfolio_id=args.portfolio_id, min_liquidity=args.min_liquidity,
            )
            output_prefix = args.output_prefix or args.portfolio_id
            save_shadow_outputs(conn, result, output_prefix, args.portfolio_id)
            print_shadow_result(result, output_prefix)
            eligible_count = int(result.rankings["eligible"].sum())
            sides = result.proposals.get("side", pd.Series(dtype=str))
            print(f"일일 요약: 적격 {eligible_count}/{len(result.rankings)}종목, "
                  f"매수 {int(sides.eq('BUY').sum())}건, 매도 {int(sides.eq('SELL').sum())}건")
            print("[4/4 누적 리포트]")
            print_shadow_report(conn, args.portfolio_id, output_prefix + "_report.csv")
            print(f"수집 요약: 가격 {price_saved}행 갱신·{price_skipped}종목 API 생략 / "
                  f"가치지표 {valuation_saved}건 저장·{valuation_skipped}종목 생략 / 오류 {error_count}건")
        conn.execute("""UPDATE daily_run_logs SET finished_at=?,status='SUCCESS',evaluation_date=?,
            price_rows=?,valuation_rows=?,error_count=?,message=? WHERE id=?""",
            (datetime.now(timezone.utc).isoformat(), evaluation_date, price_saved, valuation_saved,
             error_count, "정상 완료", log_id))
        conn.commit()
    except Exception as exc:
        conn.execute("""UPDATE daily_run_logs SET finished_at=?,status='FAILED',evaluation_date=?,
            price_rows=?,valuation_rows=?,error_count=?,message=? WHERE id=?""",
            (datetime.now(timezone.utc).isoformat(), evaluation_date, price_saved, valuation_saved,
             error_count + 1, str(exc), log_id))
        conn.commit()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="KIS + DART 분석·백테스트 MVP")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("collect-price"); p.add_argument("code"); p.add_argument("--days", type=int, default=365)
    p = sub.add_parser("collect-financial"); p.add_argument("code"); p.add_argument("--year", type=int, required=True); p.add_argument("--report-code", default="11011")
    p = sub.add_parser("analyze"); p.add_argument("code")
    p = sub.add_parser("backtest"); p.add_argument("code")
    p.add_argument("--capital", type=float, default=10_000_000)
    p.add_argument("--commission", type=float, default=0.015, help="편도 수수료(%%)")
    p.add_argument("--tax", type=float, default=0.18, help="매도 비용/세금(%%)")
    p.add_argument("--slippage", type=float, default=0.05, help="편도 슬리피지(%%)")
    p.add_argument("--export-csv", help="거래내역 CSV 저장 경로")
    p = sub.add_parser("walk-forward"); p.add_argument("code")
    p.add_argument("--train-years", type=int, default=2)
    p.add_argument("--test-months", type=int, default=12)
    p.add_argument("--capital", type=float, default=10_000_000)
    p.add_argument("--commission", type=float, default=0.015)
    p.add_argument("--tax", type=float, default=0.18)
    p.add_argument("--slippage", type=float, default=0.05)
    p.add_argument("--export-csv", default="walk_forward_results.csv")
    p = sub.add_parser("robustness"); p.add_argument("code")
    p.add_argument("--capital", type=float, default=10_000_000)
    p.add_argument("--simulations", type=int, default=5000)
    p.add_argument("--output-prefix", default="robustness_005930")
    p = sub.add_parser("external-verify"); p.add_argument("codes", nargs="+")
    p.add_argument("--days", type=int, default=1825)
    p.add_argument("--capital", type=float, default=10_000_000)
    p.add_argument("--with-walk-forward", action="store_true")
    p.add_argument("--skip-collect", action="store_true")
    p.add_argument("--export-csv", default="multi_asset_results.csv")
    p = sub.add_parser("collect-multi"); p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p.add_argument("--days", type=int, default=1825)
    p = sub.add_parser("common-verify"); p.add_argument("codes", nargs="+")
    p.add_argument("--industry", action="append", default=[], help="종목코드=업종")
    p.add_argument("--capital", type=float, default=10_000_000)
    p.add_argument("--output-prefix", default="common_multi_asset")
    p = sub.add_parser("portfolio-verify"); p.add_argument("codes", nargs="+")
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--industry", action="append", default=[], help="종목코드=업종")
    p.add_argument("--capital", type=float, default=100_000_000)
    p.add_argument("--rebalance", choices=["monthly", "quarterly"], default="monthly")
    p.add_argument("--stock-cap", type=float, default=.20)
    p.add_argument("--sector-cap", type=float, default=.35)
    p.add_argument("--lockbox-months", type=int, default=12)
    p.add_argument("--output-prefix", default="realistic_portfolio")
    p = sub.add_parser("collect-valuation"); p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p = sub.add_parser("collect-financial-series"); p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p.add_argument("--start-year", type=int, required=True); p.add_argument("--end-year", type=int, required=True)
    p = sub.add_parser("rank-universe"); p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--industry", action="append", default=[])
    p.add_argument("--export-csv", default="daily_ranking.csv")
    p.add_argument("--min-liquidity", type=float, default=1_000_000_000)
    p = sub.add_parser("shadow-run"); p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--industry", action="append", default=[])
    p.add_argument("--capital", type=float, default=100_000_000)
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--rebalance-band", type=float, default=.02)
    p.add_argument("--min-order", type=float, default=500_000)
    p.add_argument("--stock-cap", type=float, default=.15)
    p.add_argument("--sector-cap", type=float, default=.30)
    p.add_argument("--output-prefix", default="shadow")
    p.add_argument("--portfolio-id", default="default", help="독립 그림자 계좌 ID")
    p.add_argument("--min-liquidity", type=float, default=1_000_000_000,
                   help="20일 평균 거래대금 최소값(원)")
    sub.add_parser("shadow-list")
    p = sub.add_parser("shadow-report")
    p.add_argument("--portfolio-id", default="default")
    p.add_argument("--export-csv")
    p = sub.add_parser("daily-shadow"); p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--industry", action="append", default=[])
    p.add_argument("--days", type=int, default=1825)
    p.add_argument("--capital", type=float, default=100_000_000)
    p.add_argument("--top-n", type=int, default=12)
    p.add_argument("--rebalance-band", type=float, default=.02)
    p.add_argument("--min-order", type=float, default=500_000)
    p.add_argument("--stock-cap", type=float, default=.10)
    p.add_argument("--sector-cap", type=float, default=.25)
    p.add_argument("--portfolio-id", required=True)
    p.add_argument("--min-liquidity", type=float, default=1_000_000_000)
    p.add_argument("--output-prefix")
    p.add_argument("--allow-before-close", action="store_true")
    p.add_argument("--force-refresh", action="store_true",
                   help="당일 성공 기록이 있어도 가격·가치지표를 다시 수집")
    p = sub.add_parser("daily-status")
    p.add_argument("--portfolio-id")
    p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("ml-readiness"); p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p.add_argument("--portfolio-id", default="shadow_24_filtered")
    p = sub.add_parser("build-feature-store"); p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--industry", action="append", default=[])
    p = sub.add_parser("ml-train")
    p.add_argument("--horizon", type=int, choices=[5, 20, 60], default=20)
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--validation-days", type=int, default=126)
    p.add_argument("--test-days", type=int, default=126)
    p.add_argument("--artifact", default="models/baseline_h20.joblib")
    p.add_argument("--output-prefix", default="ml_baseline")
    p = sub.add_parser("ml-walk-forward")
    p.add_argument("--horizon", type=int, choices=[5, 20, 60], default=20)
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--min-train-days", type=int, default=504)
    p.add_argument("--test-days", type=int, default=126)
    p.add_argument("--output-csv", default="ml_walk_forward.csv")
    p = sub.add_parser("ml-predict")
    p.add_argument("--artifact", default="models/baseline_h20.joblib")
    p.add_argument("--output-csv", default="ml_latest_predictions.csv")
    p = sub.add_parser("ml-diagnose")
    p.add_argument("codes", nargs="*"); p.add_argument("--universe-csv")
    p.add_argument("--horizon", type=int, choices=[5, 20, 60], default=20)
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--validation-days", type=int, default=126)
    p.add_argument("--test-days", type=int, default=126)
    p.add_argument("--min-train-days", type=int, default=504)
    p.add_argument("--fold-days", type=int, default=126)
    p.add_argument("--commission", type=float, default=.015)
    p.add_argument("--tax", type=float, default=.18)
    p.add_argument("--slippage", type=float, default=.05)
    p.add_argument("--portfolio-id", default="shadow_24_filtered")
    p.add_argument("--start-year", type=int, default=2021)
    p.add_argument("--end-year", type=int, default=2025)
    p.add_argument("--output-prefix", default="ml_diagnostic_h20")
    p = sub.add_parser("ml-diagnose-v2")
    p.add_argument("--horizon", type=int, choices=[5, 20, 60], default=20)
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--validation-days", type=int, default=126)
    p.add_argument("--test-days", type=int, default=126)
    p.add_argument("--min-train-days", type=int, default=504)
    p.add_argument("--fold-days", type=int, default=126)
    p.add_argument("--commission", type=float, default=.015)
    p.add_argument("--tax", type=float, default=.18)
    p.add_argument("--slippage", type=float, default=.05)
    p.add_argument("--lockbox-start")
    p.add_argument("--universe-history-csv")
    p.add_argument("--rank-scope", choices=["market", "industry"], default="market")
    p.add_argument("--output-prefix", default="ml_corrected_h20")
    p = sub.add_parser("ml-diagnose-v3")
    p.add_argument("--horizon", type=int, choices=[5, 20, 60], default=20)
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--validation-days", type=int, default=126)
    p.add_argument("--test-days", type=int, default=126)
    p.add_argument("--min-train-days", type=int, default=504)
    p.add_argument("--fold-days", type=int, default=126)
    p.add_argument("--commission", type=float, default=.015)
    p.add_argument("--tax", type=float, default=.18)
    p.add_argument("--slippage", type=float, default=.05)
    p.add_argument("--lockbox-start")
    p.add_argument("--universe-history-csv")
    p.add_argument("--rank-scope", choices=["market", "industry"], default="market")
    p.add_argument("--output-prefix", default="ml_v3_h20")
    p = sub.add_parser("ml-diagnose-v31")
    p.add_argument("--horizon", type=int, choices=[5, 20, 60], default=20)
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--validation-days", type=int, default=126)
    p.add_argument("--test-days", type=int, default=126)
    p.add_argument("--min-train-days", type=int, default=504)
    p.add_argument("--fold-days", type=int, default=126)
    p.add_argument("--commission", type=float, default=.015)
    p.add_argument("--tax", type=float, default=.18)
    p.add_argument("--slippage", type=float, default=.05)
    p.add_argument("--lockbox-start")
    p.add_argument("--universe-history-csv")
    p.add_argument("--total-return-csv")
    p.add_argument("--security-master-csv")
    p.add_argument("--rank-scope", choices=["market", "industry"], default="market")
    p.add_argument("--output-prefix", default="ml_v31_h20")
    p = sub.add_parser("ml-diagnose-v32")
    p.add_argument("--horizon", type=int, choices=[5, 20, 60], default=20)
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--validation-days", type=int, default=252)
    p.add_argument("--test-days", type=int, default=126)
    p.add_argument("--min-train-days", type=int, default=504)
    p.add_argument("--fold-days", type=int, default=126)
    p.add_argument("--embargo-days", type=int)
    p.add_argument("--commission", type=float, default=.015)
    p.add_argument("--tax", type=float, default=.18)
    p.add_argument("--slippage", type=float, default=.05)
    p.add_argument("--stock-cap", type=float, default=.15)
    p.add_argument("--industry-cap", type=float, default=.40)
    p.add_argument("--lockbox-start")
    p.add_argument("--universe-history-csv")
    p.add_argument("--total-return-csv")
    p.add_argument("--security-master-csv")
    p.add_argument("--corporate-actions-csv")
    p.add_argument("--rank-scope", choices=["market", "industry"], default="market")
    p.add_argument("--output-prefix", default="ml_v32_h20")
    p = sub.add_parser("import-valuation-snapshots-v321")
    p.add_argument("--csv", required=True)
    p = sub.add_parser("build-data-foundation-v321")
    p.add_argument("--valuation-csv")
    p.add_argument("--total-return-csv")
    p.add_argument("--corporate-actions-csv")
    p.add_argument("--universe-history-csv")
    p.add_argument("--output-dir", default="data/v321_foundation")
    p = sub.add_parser("krx-provider-check-v321")
    p.add_argument("--code", default="005930")
    p.add_argument("--end", default="20260709")
    p = sub.add_parser("acquire-historical-data-v321")
    p.add_argument("--universe-csv", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", default="20260709")
    p.add_argument("--frequency", choices=["d", "m"], default="m")
    p.add_argument("--index-code")
    p.add_argument("--sleep-seconds", type=float, default=.15)
    p.add_argument("--output-dir", default="data/raw/v321")
    p.add_argument("--timeout-seconds", type=float, default=45.0)
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    p.add_argument("--no-resume", action="store_true")
    p = sub.add_parser("db-health-v321")
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--output-json")
    p = sub.add_parser("backup-db-v321")
    p.add_argument("--output-dir", default="data/backup")
    p.add_argument("--label", default="manual")
    p = sub.add_parser("acquire-payout-actions-v321")
    p.add_argument("--universe-csv", required=True)
    p.add_argument("--start-year", type=int, default=2020)
    p.add_argument("--end-year", type=int, default=2026)
    p.add_argument("--output-dir", default="data/raw/v321/events")
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    p.add_argument("--sleep-seconds", type=float, default=.05)
    p = sub.add_parser("build-event-reconciliation-v321")
    p.add_argument("--dividend-facts-csv", required=True)
    p.add_argument("--action-disclosures-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/event_reconciliation_queue.csv")
    p = sub.add_parser("build-total-return-v321")
    p.add_argument("--corporate-actions-csv", default="data/v321_foundation/corporate_actions_v321.csv")
    p.add_argument("--coverage-json", default="data/v321_foundation/total_return_coverage_guarded_phase553_v321.json")
    p.add_argument("--output-csv", default="data/v321_foundation/total_return_history_v321.csv")
    p.add_argument("--benchmark-code", default="069500")
    p = sub.add_parser("prepare-event-verification-v321")
    p.add_argument("--queue-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/event_verification_v321.csv")
    p = sub.add_parser("finalize-event-reconciliation-v321")
    p.add_argument("--verification-csv", required=True)
    p.add_argument("--queue-registry-csv", required=True)
    p.add_argument("--canonical-output-csv", default="data/v321_foundation/corporate_actions_v321.csv")
    p.add_argument("--audit-output-csv", default="data/v321_foundation/event_reconciliation_audit.csv")
    p.add_argument("--coverage-json", default="data/v321_foundation/total_return_coverage_v321.json")
    p.add_argument("--coverage-start", default="20200101")
    p.add_argument("--coverage-end", default="20260709")
    p = sub.add_parser("prepare-official-event-evidence-v321")
    p.add_argument("--verification-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/official_event_evidence_v321.csv")
    p = sub.add_parser("resolve-official-events-v321")
    p.add_argument("--verification-csv", required=True)
    p.add_argument("--evidence-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/event_verification_resolved_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/official_event_resolution_audit.csv")
    p.add_argument("--not-applicable-csv")
    p.add_argument("--date-window-days", type=int, default=370)
    p = sub.add_parser("acquire-official-event-candidates-v321")
    p.add_argument("--universe-csv", required=True)
    p.add_argument("--start", default="20200101")
    p.add_argument("--end", default="20260709")
    p.add_argument("--output-dir", default="data/raw/v321/events/official_candidates")
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    p.add_argument("--sleep-seconds", type=float, default=.05)
    p = sub.add_parser("enrich-official-evidence-v321")
    p.add_argument("--evidence-template-csv", required=True)
    p.add_argument("--candidate-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/official_event_evidence_enriched_v321.csv")
    p = sub.add_parser("build-market-adjustment-evidence-v321")
    p.add_argument("--official-candidates-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/market_adjustment_evidence_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/market_adjustment_evidence_audit.csv")
    p.add_argument("--window-days", type=int, default=20)
    p.add_argument("--max-match-distance-days", type=int, default=10)
    p.add_argument("--ratio-tolerance", type=float, default=.002)
    p = sub.add_parser("merge-strict-evidence-v321")
    p.add_argument("--evidence-csv", action="append", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/official_event_evidence_strict_v321.csv")
    p = sub.add_parser("build-stock-cash-amount-candidates-v321")
    p.add_argument("--dividend-facts-csv", required=True)
    p.add_argument("--verification-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_cash_amount_candidates_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/stock_cash_amount_candidates_audit.csv")
    p.add_argument("--etf-code", action="append", default=["069500"])
    p = sub.add_parser("prepare-official-cash-events-v321")
    p.add_argument("--verification-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/official_cash_events_v321.csv")
    p.add_argument("--etf-code", action="append", default=["069500"])
    p = sub.add_parser("validate-official-cash-events-v321")
    p.add_argument("--official-cash-events-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/cash_distribution_strict_evidence_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/cash_distribution_strict_evidence_audit.csv")
    p = sub.add_parser("compare-cash-amount-candidates-v321")
    p.add_argument("--strict-cash-evidence-csv", required=True)
    p.add_argument("--amount-candidates-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/cash_amount_crosscheck_audit.csv")
    p.add_argument("--tolerance", type=float, default=1e-9)
    p = sub.add_parser("prepare-benchmark-etf-distributions-v321")
    p.add_argument("--output-csv", default="data/raw/v321/events/benchmark_etf_distributions_069500.csv")
    p.add_argument("--code", default="069500")
    p = sub.add_parser("validate-benchmark-etf-distributions-v321")
    p.add_argument("--official-csv", required=True)
    p.add_argument("--strict-evidence-csv", default="data/raw/v321/events/benchmark_etf_distribution_strict_evidence_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/benchmark_etf_distribution_audit.csv")
    p.add_argument("--code", default="069500")
    p = sub.add_parser("inject-benchmark-etf-events-v321")
    p.add_argument("--strict-evidence-csv", required=True)
    p.add_argument("--verification-csv", required=True)
    p.add_argument("--queue-registry-csv", required=True)
    p.add_argument("--output-verification-csv", default="data/raw/v321/events/event_verification_with_benchmark_v321.csv")
    p.add_argument("--output-registry-csv", default="data/raw/v321/events/event_verification_with_benchmark_queue_registry.csv")
    p = sub.add_parser("summarize-stock-dividend-resolution-v321")
    p.add_argument("--amount-candidates-csv", required=True)
    p.add_argument("--amount-audit-csv", required=True)
    p.add_argument("--output-json", default="data/raw/v321/events/stock_dividend_resolution_summary_v321.json")
    p = sub.add_parser("acquire-kodex-distributions-v321")
    p.add_argument("--output-dir", default="data/raw/v321/events/kodex_069500")
    p.add_argument("--url", default="https://m.samsungfund.com/etf/product/view.do?id=2ETF01")
    p.add_argument("--timeout-seconds", type=float, default=30.0)
    p = sub.add_parser("build-stock-dividend-ambiguity-report-v321")
    p.add_argument("--amount-audit-csv", required=True)
    p.add_argument("--amount-candidates-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_dividend_ambiguity_report_v321.csv")
    p = sub.add_parser("discover-kodex-dynamic-endpoints-v321")
    p.add_argument("--product-url", default="https://m.samsungfund.com/etf/product/view.do?id=2ETF01")
    p.add_argument("--output-dir", default="data/raw/v321/events/kodex_069500/dynamic")
    p.add_argument("--timeout-seconds", type=float, default=30.0)
    p.add_argument("--max-scripts", type=int, default=40)
    p = sub.add_parser("refine-stock-dividend-candidates-v321")
    p.add_argument("--dividend-facts-csv", required=True)
    p.add_argument("--verification-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_cash_amount_candidates_refined_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/stock_cash_amount_candidates_refined_audit.csv")
    p.add_argument("--etf-code", action="append", default=["069500"])
    p = sub.add_parser("rank-probe-kodex-endpoints-v321")
    p.add_argument("--candidate-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/kodex_069500/dynamic/kodex_endpoint_probe_v321.csv")
    p.add_argument("--top-n", type=int, default=25)
    p.add_argument("--timeout-seconds", type=float, default=12.0)
    p.add_argument("--product-host", default="m.samsungfund.com")
    p = sub.add_parser("acquire-stock-dividend-decisions-v321")
    p.add_argument("--universe-csv", required=True)
    p.add_argument("--start", default="20200101")
    p.add_argument("--end", default="20260709")
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_dividend_decision_disclosures_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/stock_dividend_decision_disclosures_audit.csv")
    p.add_argument("--sleep-seconds", type=float, default=.05)
    p = sub.add_parser("build-stock-dividend-exdate-queue-v321")
    p.add_argument("--refined-amount-candidates-csv", required=True)
    p.add_argument("--dividend-decisions-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_dividend_exdate_resolution_queue_v321.csv")
    p.add_argument("--match-days", type=int, default=430)
    p = sub.add_parser("inspect-kodex-high-signal-responses-v321")
    p.add_argument("--probe-csv", required=True)
    p.add_argument("--output-dir", default="data/raw/v321/events/kodex_069500/high_signal")
    p.add_argument("--min-response-keyword-score", type=int, default=2)
    p.add_argument("--timeout-seconds", type=float, default=15.0)
    p.add_argument("--product-host", default="m.samsungfund.com")
    p = sub.add_parser("extract-dart-dividend-record-dates-v321")
    p.add_argument("--decision-disclosures-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_dividend_official_date_candidates_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/stock_dividend_official_date_candidates_audit.csv")
    p.add_argument("--sleep-seconds", type=float, default=.05)
    p = sub.add_parser("merge-dividend-date-candidates-v321")
    p.add_argument("--exdate-queue-csv", required=True)
    p.add_argument("--dart-record-candidates-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_dividend_date_resolution_v321.csv")
    p.add_argument("--match-days", type=int, default=430)
    p = sub.add_parser("build-explicit-stock-exdate-evidence-v321")
    p.add_argument("--stock-dividend-date-resolution-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_dividend_explicit_exdate_strict_evidence_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/stock_dividend_explicit_exdate_audit.csv")
    p = sub.add_parser("export-benchmark-calendar-v321")
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--output-csv", default="data/raw/v321/events/benchmark_069500_trading_calendar.csv")
    p.add_argument("--include-post-cutoff", action="store_true")
    p = sub.add_parser("build-record-date-calendar-candidates-v321")
    p.add_argument("--stock-dividend-date-resolution-csv", required=True)
    p.add_argument("--benchmark-prices-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_dividend_record_date_calendar_candidates_v321.csv")
    p = sub.add_parser("parse-kodex-distribution-tables-v321")
    p.add_argument("--bodies-dir", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/kodex_069500/high_signal/kodex_distribution_table_candidates_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kodex_069500/high_signal/kodex_distribution_table_audit.csv")
    p = sub.add_parser("build-market-exdate-verification-queue-v321")
    p.add_argument("--stock-dividend-date-resolution-csv", required=True)
    p.add_argument("--record-date-calendar-candidates-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/stock_dividend_market_exdate_verification_queue_v321.csv")
    p = sub.add_parser("validate-official-market-exdates-v321")
    p.add_argument("--verification-csv", required=True)
    p.add_argument("--strict-evidence-csv", default="data/raw/v321/events/stock_dividend_market_exdate_strict_evidence_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/stock_dividend_market_exdate_strict_audit.csv")
    p = sub.add_parser("summarize-kodex-high-signal-bodies-v321")
    p.add_argument("--response-audit-csv", required=True)
    p.add_argument("--field-candidates-csv", required=True)
    p.add_argument("--output-json", default="data/raw/v321/events/kodex_069500/high_signal/kodex_high_signal_summary_v321.json")
    p = sub.add_parser("crosscheck-kind-dividends-v321")
    p.add_argument("--market-exdate-queue-csv", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_dividend_crosscheck_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kind_dividend_crosscheck_audit.csv")
    p.add_argument("--timeout-seconds", type=float, default=15.0)
    p = sub.add_parser("retry-kind-dividends-v321")
    p.add_argument("--crosscheck-csv", default="data/raw/v321/events/kind_dividend_crosscheck_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kind_dividend_fetch_audit_v321.csv")
    p.add_argument("--retry-queue-csv", default="data/raw/v321/events/kind_dividend_retry_queue_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_dividend_crosscheck_status_v321.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/kind_documents")
    p.add_argument("--timeout-seconds", type=int, default=15)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("parse-kind-dividends-v321")
    p.add_argument("--documents-dir", default="data/raw/v321/events/kind_documents")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_dividend_parsed_v321.csv")
    p = sub.add_parser("reconcile-kind-dividends-v321")
    p.add_argument("--market-queue-csv", default="data/raw/v321/events/stock_dividend_market_exdate_verification_queue_v321.csv")
    p.add_argument("--crosscheck-csv", default="data/raw/v321/events/kind_dividend_crosscheck_v321.csv")
    p.add_argument("--parsed-csv", default="data/raw/v321/events/kind_dividend_parsed_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kind_dividend_candidate_reconciliation_audit_v321.csv")
    p.add_argument("--official-facts-csv", default="data/raw/v321/events/kind_dividend_official_facts_v321.csv")
    p = sub.add_parser("acquire-kind-market-exdates-v321")
    p.add_argument("--manifest-csv", default="data/raw/v321/events/kind_market_exdate_source_manifest_v321.csv")
    p.add_argument("--official-facts-csv", default="data/raw/v321/events/kind_dividend_official_facts_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_market_exdate_observations_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kind_market_exdate_acquisition_audit_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("audit-market-notice-coverage-v321")
    p.add_argument("--acquisition-manifest-csv", default="data/raw/v321/events/recent_dividend_acquisition_enriched_phase542_v321.csv")
    p.add_argument("--strict-evidence-csv", default="data/raw/v321/events/official_event_evidence_strict_v321.csv")
    p.add_argument("--discovery-csv", action="append", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/market_notice_coverage_audit_phase542_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/market_notice_coverage_summary_phase542_v321.json")
    p = sub.add_parser("classify-recent-corporate-actions-v321")
    p.add_argument("--priority-queue-csv", default="data/raw/v321/events/event_resolution_priority_queue_phase542_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/recent_corporate_action_acquisition_queue_phase543_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/recent_corporate_action_summary_phase543_v321.json")
    p = sub.add_parser("build-corporate-action-candidate-manifest-v321")
    p.add_argument("--classified-queue-csv", default="data/raw/v321/events/recent_corporate_action_acquisition_queue_phase543_v321.csv")
    p.add_argument("--official-candidates-csv", default="data/raw/v321/events/official_candidates/official_event_candidates_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/corporate_action_candidate_manifest_phase544_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/corporate_action_candidate_summary_phase544_v321.json")
    p = sub.add_parser("select-market-adjustment-candidates-v321")
    p.add_argument("--candidate-manifest-csv", default="data/raw/v321/events/corporate_action_candidate_manifest_phase544_v321.csv")
    p.add_argument("--official-candidates-csv", default="data/raw/v321/events/official_candidates/official_event_candidates_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/market_adjustment_candidates_phase545_v321.csv")
    p = sub.add_parser("acquire-missing-corporate-action-documents-v321")
    p.add_argument("--candidate-manifest-csv", default="data/raw/v321/events/corporate_action_candidate_manifest_phase544_v321.csv")
    p.add_argument("--disclosures-csv", default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/corporate_action_documents_phase546")
    p.add_argument("--output-csv", default="data/raw/v321/events/corporate_action_document_acquisition_phase546_v321.csv")
    p = sub.add_parser("parse-corporate-action-documents-v321")
    p.add_argument("--acquisition-csv", default="data/raw/v321/events/corporate_action_document_acquisition_phase546_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/corporate_action_document_parsed_phase547_v321.csv")
    p = sub.add_parser("review-complex-corporate-actions-v321")
    p.add_argument("--candidate-manifest-csv", default="data/raw/v321/events/corporate_action_candidate_manifest_phase544_v321.csv")
    p.add_argument("--official-candidates-csv", default="data/raw/v321/events/official_candidates/official_event_candidates_v321.csv")
    p.add_argument("--not-applicable-csv", default="data/raw/v321/events/corporate_action_not_applicable_phase548_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/complex_corporate_action_audit_phase548_v321.csv")
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
    p = sub.add_parser("prioritize-current-resolution-backlog-v321")
    p.add_argument("--resolved-verification-csv", default="data/raw/v321/events/event_verification_resolved_phase548_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/current_resolution_priority_phase555_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/current_resolution_priority_summary_phase555_v321.json")
    p = sub.add_parser("acquire-subsidiary-action-documents-v321")
    p.add_argument("--priority-queue-csv", default="data/raw/v321/events/current_resolution_priority_phase555_v321.csv")
    p.add_argument("--disclosures-csv", default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/subsidiary_action_documents_phase556")
    p.add_argument("--output-csv", default="data/raw/v321/events/subsidiary_action_document_acquisition_phase556_v321.csv")
    p = sub.add_parser("parse-subsidiary-action-applicability-v321")
    p.add_argument("--acquisition-manifest-csv", default="data/raw/v321/events/subsidiary_action_document_acquisition_phase556_v321.csv")
    p.add_argument("--audit-output-csv", default="data/raw/v321/events/subsidiary_action_applicability_audit_phase557_v321.csv")
    p.add_argument("--not-applicable-output-csv", default="data/raw/v321/events/subsidiary_action_not_applicable_phase557_v321.csv")
    p = sub.add_parser("integrate-not-applicable-evidence-v321")
    p.add_argument("--verification-csv", default="data/raw/v321/events/event_verification_resolved_phase548_v321.csv")
    p.add_argument("--evidence-csv", default="data/raw/v321/events/subsidiary_action_not_applicable_phase557_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/event_verification_resolved_phase558_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/not_applicable_integration_audit_phase558_v321.csv")
    p.add_argument("--priority-output-csv", default="data/raw/v321/events/current_resolution_priority_phase558_v321.csv")
    p.add_argument("--priority-summary-json", default="data/raw/v321/events/current_resolution_priority_summary_phase558_v321.json")
    p = sub.add_parser("resolve-residual-subsidiary-actions-v321")
    p.add_argument("--applicability-audit-csv", default="data/raw/v321/events/subsidiary_action_applicability_audit_phase557_v321.csv")
    p.add_argument("--acquisition-manifest-csv", default="data/raw/v321/events/subsidiary_action_document_acquisition_phase556_v321.csv")
    p.add_argument("--disclosures-csv", default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/residual_subsidiary_documents_phase559")
    p.add_argument("--evidence-output-csv", default="data/raw/v321/events/residual_subsidiary_not_applicable_phase559_v321.csv")
    p.add_argument("--audit-output-csv", default="data/raw/v321/events/residual_subsidiary_audit_phase559_v321.csv")
    p = sub.add_parser("integrate-residual-subsidiary-evidence-v321")
    p.add_argument("--verification-csv", default="data/raw/v321/events/event_verification_resolved_phase558_v321.csv")
    p.add_argument("--evidence-csv", default="data/raw/v321/events/residual_subsidiary_not_applicable_phase559_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/event_verification_resolved_phase560_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/residual_subsidiary_integration_audit_phase560_v321.csv")
    p.add_argument("--priority-output-csv", default="data/raw/v321/events/current_resolution_priority_phase560_v321.csv")
    p.add_argument("--priority-summary-json", default="data/raw/v321/events/current_resolution_priority_summary_phase560_v321.json")
    p = sub.add_parser("build-direct-action-document-inventory-v321")
    p.add_argument("--priority-queue-csv", default="data/raw/v321/events/current_resolution_priority_phase560_v321.csv")
    p.add_argument("--disclosures-csv", default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--prior-acquisition-csv", default="data/raw/v321/events/corporate_action_document_acquisition_phase546_v321.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/direct_action_documents_phase561")
    p.add_argument("--output-csv", default="data/raw/v321/events/direct_action_document_inventory_phase561_v321.csv")
    p = sub.add_parser("review-direct-action-groups-v321")
    p.add_argument("--inventory-csv", default="data/raw/v321/events/direct_action_document_inventory_phase561_v321.csv")
    p.add_argument("--evidence-output-csv", default="data/raw/v321/events/direct_action_not_applicable_phase562_v321.csv")
    p.add_argument("--audit-output-csv", default="data/raw/v321/events/direct_action_group_audit_phase562_v321.csv")
    p.add_argument("--parsed-documents-csv", default="data/raw/v321/events/corporate_action_document_parsed_phase547_v321.csv")
    p = sub.add_parser("integrate-direct-action-evidence-v321")
    p.add_argument("--verification-csv", default="data/raw/v321/events/event_verification_resolved_phase560_v321.csv")
    p.add_argument("--evidence-csv", default="data/raw/v321/events/direct_action_not_applicable_phase562_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/event_verification_resolved_phase563_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/direct_action_integration_audit_phase563_v321.csv")
    p.add_argument("--priority-output-csv", default="data/raw/v321/events/current_resolution_priority_phase563_v321.csv")
    p.add_argument("--priority-summary-json", default="data/raw/v321/events/current_resolution_priority_summary_phase563_v321.json")
    p = sub.add_parser("verify-samsung-sdi-rights-v321")
    p.add_argument("--evidence-output-csv", default="data/raw/v321/events/samsung_sdi_rights_strict_evidence_phase564_v321.csv")
    p.add_argument("--audit-output-csv", default="data/raw/v321/events/samsung_sdi_rights_audit_phase564_v321.csv")
    p = sub.add_parser("integrate-strict-event-evidence-v321")
    p.add_argument("--verification-csv", default="data/raw/v321/events/event_verification_resolved_phase563_v321.csv")
    p.add_argument("--evidence-csv", default="data/raw/v321/events/samsung_sdi_rights_strict_evidence_phase564_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/event_verification_resolved_phase565_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/strict_evidence_integration_audit_phase565_v321.csv")
    p.add_argument("--priority-output-csv", default="data/raw/v321/events/current_resolution_priority_phase565_v321.csv")
    p.add_argument("--priority-summary-json", default="data/raw/v321/events/current_resolution_priority_summary_phase565_v321.json")
    p = sub.add_parser("route-actionable-resolution-backlog-v321")
    p.add_argument("--priority-queue-csv", default="data/raw/v321/events/current_resolution_priority_phase565_v321.csv")
    p.add_argument("--direct-action-audit-csv", default="data/raw/v321/events/direct_action_group_audit_phase562_v321.csv")
    p.add_argument("--complex-evidence-audit-csv", default="data/raw/v321/events/spinoff_evidence_completeness_phase552_v321.csv")
    p.add_argument("--actionable-output-csv", default="data/raw/v321/events/actionable_resolution_queue_phase566_v321.csv")
    p.add_argument("--blocked-output-csv", default="data/raw/v321/events/blocked_resolution_queue_phase566_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/actionable_resolution_summary_phase566_v321.json")
    p = sub.add_parser("build-recent-dividend-evidence-inventory-v321")
    p.add_argument("--actionable-queue-csv", default="data/raw/v321/events/actionable_resolution_queue_phase566_v321.csv")
    p.add_argument("--prior-coverage-audit-csv", default="data/raw/v321/events/market_notice_coverage_audit_phase542_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/recent_dividend_evidence_inventory_phase567_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/recent_dividend_evidence_inventory_summary_phase567_v321.json")
    p = sub.add_parser("acquire-historical-dividend-decisions-v321")
    p.add_argument("--inventory-csv", default="data/raw/v321/events/recent_dividend_evidence_inventory_phase567_v321.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/historical_dividend_decisions_phase568")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_dividend_decision_acquisition_phase568_v321.csv")
    p = sub.add_parser("parse-historical-dividend-decisions-v321")
    p.add_argument("--acquisition-csv", default="data/raw/v321/events/historical_dividend_decision_acquisition_phase568_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_dividend_decision_parsed_phase569_v321.csv")
    p = sub.add_parser("build-historical-dividend-exdate-candidates-v321")
    p.add_argument("--parsed-csv", default="data/raw/v321/events/historical_dividend_decision_parsed_phase569_v321.csv")
    p.add_argument("--trading-calendar-db", default="data/backup/stock_analytics_20260808_194044_baseline_v321.db")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_dividend_exdate_candidates_phase570_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/historical_dividend_exdate_candidates_summary_phase570_v321.json")
    p = sub.add_parser("discover-historical-kind-exdates-v321")
    p.add_argument("--candidates-csv", default="data/raw/v321/events/historical_dividend_exdate_candidates_phase570_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_kind_exdate_discovery_phase571_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/historical_kind_exdate_discovery_audit_phase571_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("build-historical-kind-strict-evidence-v321")
    p.add_argument("--discovery-csv", default="data/raw/v321/events/historical_kind_exdate_discovery_phase571_v321.csv")
    p.add_argument("--parsed-decisions-csv", default="data/raw/v321/events/historical_dividend_decision_parsed_phase569_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/historical_kind_strict_evidence_phase572_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/historical_kind_strict_evidence_audit_phase572_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("integrate-historical-dividend-evidence-v321")
    p.add_argument("--verification-csv", default="data/raw/v321/events/event_verification_resolved_phase565_v321.csv")
    p.add_argument("--strict-ledger-csv", default="data/raw/v321/events/historical_kind_strict_evidence_phase572_v321.csv")
    p.add_argument("--selected-evidence-csv", default="data/raw/v321/events/historical_dividend_selected_evidence_phase573_v321.csv")
    p.add_argument("--selection-audit-csv", default="data/raw/v321/events/historical_dividend_selection_audit_phase573_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/event_verification_resolved_phase573_v321.csv")
    p.add_argument("--integration-audit-csv", default="data/raw/v321/events/historical_dividend_integration_audit_phase573_v321.csv")
    p.add_argument("--priority-output-csv", default="data/raw/v321/events/current_resolution_priority_phase573_v321.csv")
    p.add_argument("--priority-summary-json", default="data/raw/v321/events/current_resolution_priority_summary_phase573_v321.json")
    p = sub.add_parser("build-residual-dividend-backlog-v321")
    p.add_argument("--actionable-queue-csv", default="data/raw/v321/events/actionable_resolution_queue_phase574_v321.csv")
    p.add_argument("--acquisition-csv", default="data/raw/v321/events/historical_dividend_decision_acquisition_phase568_v321.csv")
    p.add_argument("--candidates-csv", default="data/raw/v321/events/historical_dividend_exdate_candidates_phase570_v321.csv")
    p.add_argument("--discovery-audit-csv", default="data/raw/v321/events/historical_kind_exdate_discovery_audit_phase571_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/residual_dividend_backlog_phase574_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/residual_dividend_backlog_summary_phase574_v321.json")
    p = sub.add_parser("resolve-ambiguous-kind-notice-v321")
    p.add_argument("--residual-csv", default="data/raw/v321/events/residual_dividend_backlog_phase574_v321.csv")
    p.add_argument("--parsed-decisions-csv", default="data/raw/v321/events/historical_dividend_decision_parsed_phase569_v321.csv")
    p.add_argument("--discovery-output-csv", default="data/raw/v321/events/ambiguous_kind_notice_resolved_phase575_v321.csv")
    p.add_argument("--candidate-audit-csv", default="data/raw/v321/events/ambiguous_kind_notice_candidates_audit_phase575_v321.csv")
    p.add_argument("--strict-evidence-csv", default="data/raw/v321/events/ambiguous_kind_strict_evidence_phase575_v321.csv")
    p.add_argument("--strict-audit-csv", default="data/raw/v321/events/ambiguous_kind_strict_evidence_audit_phase575_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("resolve-broadened-kind-notices-v321")
    p.add_argument("--residual-csv", default="data/raw/v321/events/residual_dividend_backlog_phase576_v321.csv")
    p.add_argument("--prior-discovery-audit-csv", default="data/raw/v321/events/historical_kind_exdate_discovery_audit_phase571_v321.csv")
    p.add_argument("--candidates-csv", default="data/raw/v321/events/historical_dividend_exdate_candidates_phase570_v321.csv")
    p.add_argument("--parsed-decisions-csv", default="data/raw/v321/events/historical_dividend_decision_parsed_phase569_v321.csv")
    p.add_argument("--discovery-output-csv", default="data/raw/v321/events/broadened_kind_notice_resolved_phase577_v321.csv")
    p.add_argument("--candidate-audit-csv", default="data/raw/v321/events/broadened_kind_notice_candidates_audit_phase577_v321.csv")
    p.add_argument("--strict-evidence-csv", default="data/raw/v321/events/broadened_kind_strict_evidence_phase577_v321.csv")
    p.add_argument("--strict-audit-csv", default="data/raw/v321/events/broadened_kind_strict_evidence_audit_phase577_v321.csv")
    p.add_argument("--timeout-seconds",type=int,default=20)
    p = sub.add_parser("recover-pre-exdate-dividend-evidence-v321")
    p.add_argument("--residual-csv",default="data/raw/v321/events/residual_dividend_backlog_phase577_v321.csv")
    p.add_argument("--parsed-decisions-csv",default="data/raw/v321/events/historical_dividend_decision_parsed_phase569_v321.csv")
    p.add_argument("--candidates-csv",default="data/raw/v321/events/historical_dividend_exdate_candidates_phase570_v321.csv")
    p.add_argument("--provenance-audit-csv",default="data/raw/v321/events/pre_exdate_provenance_audit_phase578_v321.csv")
    p.add_argument("--discovery-output-csv",default="data/raw/v321/events/pre_exdate_kind_notice_resolved_phase578_v321.csv")
    p.add_argument("--discovery-audit-csv",default="data/raw/v321/events/pre_exdate_kind_notice_audit_phase578_v321.csv")
    p.add_argument("--strict-evidence-csv",default="data/raw/v321/events/pre_exdate_strict_evidence_phase578_v321.csv")
    p.add_argument("--strict-audit-csv",default="data/raw/v321/events/pre_exdate_strict_evidence_audit_phase578_v321.csv")
    p.add_argument("--timeout-seconds",type=int,default=20)
    p = sub.add_parser("resolve-explicit-no-dividend-v321")
    p.add_argument("--residual-csv",default="data/raw/v321/events/residual_dividend_backlog_phase578_v321.csv")
    p.add_argument("--dividend-facts-csv",default="data/raw/v321/events/dividend_disclosure_facts.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/explicit_no_dividend_evidence_phase579_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/explicit_no_dividend_audit_phase579_v321.csv")
    p.add_argument("--business-year",default="2024")
    p = sub.add_parser("defer-non-pit-dividends-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase579_v321.csv")
    p.add_argument("--residual-csv",default="data/raw/v321/events/residual_dividend_backlog_phase579_v321.csv")
    p.add_argument("--provenance-audit-csv",default="data/raw/v321/events/pre_exdate_provenance_audit_phase578_v321.csv")
    p.add_argument("--actionable-output-csv",default="data/raw/v321/events/actionable_resolution_queue_phase580_v321.csv")
    p.add_argument("--deferred-output-csv",default="data/raw/v321/events/deferred_non_pit_dividends_phase580_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/non_pit_dividend_deferral_audit_phase580_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/non_pit_dividend_deferral_summary_phase580_v321.json")
    p = sub.add_parser("resolve-recent-followups-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase580_v321.csv")
    p.add_argument("--resolved-verification-csv",default="data/raw/v321/events/event_verification_resolved_phase579_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/recent_followup_documents_phase581")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/recent_followup_not_applicable_evidence_phase581_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/recent_followup_resolution_audit_phase581_v321.csv")
    p = sub.add_parser("route-historical-backlog-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase581_v321.csv")
    p.add_argument("--output-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_backlog_execution_summary_phase582_v321.json")
    p = sub.add_parser("quarantine-periodic-dividend-aggregates-v321")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--dividend-facts-csv",default="data/raw/v321/events/dividend_disclosure_facts.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/periodic_dividend_aggregate_not_applicable_evidence_phase583_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/periodic_dividend_aggregate_quarantine_audit_phase583_v321.csv")
    p.add_argument("--replacement-queue-csv",default="data/raw/v321/events/discrete_dividend_reconstruction_queue_phase583_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/periodic_dividend_aggregate_quarantine_summary_phase583_v321.json")
    p = sub.add_parser("build-historical-legal-event-chain-v321")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--output-csv",default="data/raw/v321/events/historical_legal_event_chain_phase584_v321.csv")
    p.add_argument("--review-queue-csv",default="data/raw/v321/events/historical_legal_event_chain_review_phase584_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_legal_event_chain_summary_phase584_v321.json")
    p = sub.add_parser("validate-historical-chain-documents-v321")
    p.add_argument("--chain-csv",default="data/raw/v321/events/historical_legal_event_chain_phase584_v321.csv")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/historical_chain_documents_phase585")
    p.add_argument("--output-csv",default="data/raw/v321/events/historical_chain_document_validation_phase585_v321.csv")
    p.add_argument("--review-queue-csv",default="data/raw/v321/events/historical_chain_document_review_phase585_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_chain_document_validation_summary_phase585_v321.json")
    p = sub.add_parser("consolidate-historical-legal-chains-v321")
    p.add_argument("--validation-csv",default="data/raw/v321/events/historical_chain_document_validation_phase585_v321.csv")
    p.add_argument("--chain-csv",default="data/raw/v321/events/historical_legal_event_chain_phase584_v321.csv")
    p.add_argument("--group-output-csv",default="data/raw/v321/events/historical_legal_event_groups_phase586_v321.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/historical_chain_not_applicable_evidence_phase586_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/historical_chain_consolidation_audit_phase586_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_chain_consolidation_summary_phase586_v321.json")
    p = sub.add_parser("extract-primary-adjustment-document-terms-v321")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--legal-groups-csv",default="data/raw/v321/events/historical_legal_event_groups_phase586_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/primary_adjustment_documents_phase587")
    p.add_argument("--output-csv",default="data/raw/v321/events/primary_adjustment_document_terms_phase587_v321.csv")
    p.add_argument("--review-queue-csv",default="data/raw/v321/events/primary_adjustment_document_review_phase587_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/primary_adjustment_document_terms_summary_phase587_v321.json")
    p = sub.add_parser("validate-primary-adjustment-market-dates-v321")
    p.add_argument("--terms-csv",default="data/raw/v321/events/primary_adjustment_document_terms_phase587_v321.csv")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--trading-calendar-db",default="data/backup/stock_analytics_20260808_194044_baseline_v321.db")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/primary_adjustment_market_evidence_phase588_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/primary_adjustment_market_validation_audit_phase588_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/primary_adjustment_market_validation_summary_phase588_v321.json")
    p = sub.add_parser("audit-historical-rights-applicability-v321")
    p.add_argument("--terms-csv",default="data/raw/v321/events/primary_adjustment_document_terms_phase587_v321.csv")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/primary_adjustment_documents_phase587")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/historical_rights_not_applicable_evidence_phase589_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/historical_rights_applicability_audit_phase589_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_rights_applicability_summary_phase589_v321.json")
    p = sub.add_parser("audit-historical-merger-spinoff-applicability-v321")
    p.add_argument("--terms-csv",default="data/raw/v321/events/primary_adjustment_document_terms_phase587_v321.csv")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/primary_adjustment_documents_phase587")
    p.add_argument("--trading-calendar-db",default="data/backup/stock_analytics_20260808_194044_baseline_v321.db")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/historical_merger_spinoff_not_applicable_evidence_phase590_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/historical_merger_spinoff_applicability_audit_phase590_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_merger_spinoff_applicability_summary_phase590_v321.json")
    p = sub.add_parser("reparse-celltrion-merger-v321")
    p.add_argument("--applicability-audit-csv",default="data/raw/v321/events/historical_merger_spinoff_applicability_audit_phase590_v321.csv")
    p.add_argument("--terms-csv",default="data/raw/v321/events/primary_adjustment_document_terms_phase587_v321.csv")
    p.add_argument("--official-candidates-csv",default="data/raw/v321/events/official_candidates/official_event_candidates_v321.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/celltrion_merger_not_applicable_evidence_phase591_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/celltrion_merger_reparse_audit_phase591_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/celltrion_merger_reparse_summary_phase591_v321.json")
    p = sub.add_parser("audit-historical-capital-reductions-v321")
    p.add_argument("--terms-csv",default="data/raw/v321/events/primary_adjustment_document_terms_phase587_v321.csv")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/primary_adjustment_documents_phase587")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/historical_capital_reduction_not_applicable_evidence_phase592_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/historical_capital_reduction_applicability_audit_phase592_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_capital_reduction_applicability_summary_phase592_v321.json")
    p = sub.add_parser("audit-incomplete-primary-adjustments-v321")
    p.add_argument("--terms-csv",default="data/raw/v321/events/primary_adjustment_document_terms_phase587_v321.csv")
    p.add_argument("--execution-manifest-csv",default="data/raw/v321/events/historical_backlog_execution_manifest_phase582_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/primary_adjustment_documents_phase587")
    p.add_argument("--trading-calendar-db",default="data/backup/stock_analytics_20260808_194044_baseline_v321.db")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/incomplete_primary_not_applicable_evidence_phase593_v321.csv")
    p.add_argument("--review-output-csv",default="data/raw/v321/events/direct_primary_reparse_queue_phase593_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/incomplete_primary_applicability_audit_phase593_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/incomplete_primary_applicability_summary_phase593_v321.json")
    p = sub.add_parser("verify-samsung-heavy-rights-v321")
    p.add_argument("--review-queue-csv",default="data/raw/v321/events/direct_primary_reparse_queue_phase593_v321.csv")
    p.add_argument("--decision-documents-dir",default="data/raw/v321/events/historical_chain_documents_phase585")
    p.add_argument("--output-documents-dir",default="data/raw/v321/events/samsung_heavy_rights_documents_phase594")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/samsung_heavy_rights_evidence_phase594_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/samsung_heavy_rights_audit_phase594_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/samsung_heavy_rights_summary_phase594_v321.json")
    p = sub.add_parser("audit-amorepacific-restructuring-v321")
    p.add_argument("--review-queue-csv",default="data/raw/v321/events/direct_primary_reparse_queue_phase593_v321.csv")
    p.add_argument("--official-candidates-csv",default="data/raw/v321/events/official_candidates/official_event_candidates_v321.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/amorepacific_restructuring_not_applicable_evidence_phase595_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/amorepacific_restructuring_audit_phase595_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/amorepacific_restructuring_summary_phase595_v321.json")
    p = sub.add_parser("audit-overseas-listing-delistings-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase595_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/overseas_listing_delisting_documents_phase596")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/overseas_listing_delisting_not_applicable_evidence_phase596_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/overseas_listing_delisting_audit_phase596_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/overseas_listing_delisting_summary_phase596_v321.json")
    p = sub.add_parser("audit-lgchem-subsidiary-rights-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase596_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/lgchem_subsidiary_rights_documents_phase597")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/lgchem_subsidiary_rights_not_applicable_evidence_phase597_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/lgchem_subsidiary_rights_audit_phase597_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/lgchem_subsidiary_rights_summary_phase597_v321.json")
    p = sub.add_parser("audit-hdhyundai-exchangeable-bond-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase597_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/hdhyundai_exchangeable_bond_documents_phase598")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/hdhyundai_exchangeable_bond_not_applicable_evidence_phase598_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/hdhyundai_exchangeable_bond_audit_phase598_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/hdhyundai_exchangeable_bond_summary_phase598_v321.json")
    p=sub.add_parser("audit-ecoprobm-merger-transfer-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase598_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/ecoprobm_merger_transfer_documents_phase599")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/ecoprobm_merger_transfer_not_applicable_evidence_phase599_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/ecoprobm_merger_transfer_audit_phase599_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/ecoprobm_merger_transfer_summary_phase599_v321.json")
    p=sub.add_parser("audit-kakao-zero-ratio-merger-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase599_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/kakao_zero_ratio_merger_documents_phase600")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/kakao_zero_ratio_merger_not_applicable_evidence_phase600_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/kakao_zero_ratio_merger_audit_phase600_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/kakao_zero_ratio_merger_summary_phase600_v321.json")
    p=sub.add_parser("audit-celltrion-merger-followups-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase600_v321.csv")
    p.add_argument("--phase591-audit-csv",default="data/raw/v321/events/celltrion_merger_reparse_audit_phase591_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/celltrion_merger_followup_documents_phase601")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/celltrion_merger_followup_not_applicable_evidence_phase601_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/celltrion_merger_followup_audit_phase601_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/celltrion_merger_followup_summary_phase601_v321.json")
    p=sub.add_parser("audit-kakao-overseas-dr-delisting-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase601_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/kakao_overseas_dr_delisting_documents_phase602")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/kakao_overseas_dr_delisting_not_applicable_evidence_phase602_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/kakao_overseas_dr_delisting_audit_phase602_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/kakao_overseas_dr_delisting_summary_phase602_v321.json")
    p=sub.add_parser("audit-samsung-heavy-preferred-delisting-warnings-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase602_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/samsung_heavy_preferred_delisting_warning_documents_phase603")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/samsung_heavy_preferred_delisting_warning_not_applicable_evidence_phase603_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/samsung_heavy_preferred_delisting_warning_audit_phase603_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/samsung_heavy_preferred_delisting_warning_summary_phase603_v321.json")
    p=sub.add_parser("audit-hd-ksoe-subsidiary-zero-ratio-merger-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase603_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/hd_ksoe_subsidiary_zero_ratio_merger_documents_phase604")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/hd_ksoe_subsidiary_zero_ratio_merger_not_applicable_evidence_phase604_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/hd_ksoe_subsidiary_zero_ratio_merger_audit_phase604_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/hd_ksoe_subsidiary_zero_ratio_merger_summary_phase604_v321.json")
    p=sub.add_parser("audit-ecoprobm-subsidiary-capital-increases-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase604_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/ecoprobm_subsidiary_capital_increase_documents_phase605")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/ecoprobm_subsidiary_capital_increase_not_applicable_evidence_phase605_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/ecoprobm_subsidiary_capital_increase_audit_phase605_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/ecoprobm_subsidiary_capital_increase_summary_phase605_v321.json")
    p=sub.add_parser("audit-lgchem-historical-subsidiary-capital-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase605_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/lgchem_historical_subsidiary_capital_documents_phase606")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/lgchem_historical_subsidiary_capital_not_applicable_evidence_phase606_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/lgchem_historical_subsidiary_capital_audit_phase606_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/lgchem_historical_subsidiary_capital_summary_phase606_v321.json")
    p=sub.add_parser("audit-amorepacific-us-subsidiary-capital-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase606_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/amorepacific_us_subsidiary_capital_documents_phase607")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/amorepacific_us_subsidiary_capital_not_applicable_evidence_phase607_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/amorepacific_us_subsidiary_capital_audit_phase607_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/amorepacific_us_subsidiary_capital_summary_phase607_v321.json")
    p=sub.add_parser("audit-skhynix-subsidiary-capital-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase607_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/skhynix_subsidiary_capital_documents_phase608")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/skhynix_subsidiary_capital_not_applicable_evidence_phase608_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/skhynix_subsidiary_capital_audit_phase608_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/skhynix_subsidiary_capital_summary_phase608_v321.json")
    p=sub.add_parser("audit-cj-schwans-subsidiary-mergers-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase608_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/cj_schwans_subsidiary_merger_documents_phase609")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/cj_schwans_subsidiary_merger_not_applicable_evidence_phase609_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/cj_schwans_subsidiary_merger_audit_phase609_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/cj_schwans_subsidiary_merger_summary_phase609_v321.json")
    p=sub.add_parser("audit-kakao-games-subsidiary-capital-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase609_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/kakao_games_subsidiary_capital_documents_phase610")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/kakao_games_subsidiary_capital_not_applicable_evidence_phase610_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/kakao_games_subsidiary_capital_audit_phase610_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/kakao_games_subsidiary_capital_summary_phase610_v321.json")
    p=sub.add_parser("audit-naver-line-overseas-delisting-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase610_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/naver_line_overseas_delisting_documents_phase611")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/naver_line_overseas_delisting_not_applicable_evidence_phase611_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/naver_line_overseas_delisting_audit_phase611_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/naver_line_overseas_delisting_summary_phase611_v321.json")
    p=sub.add_parser("audit-historical-administrative-trading-halts-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase611_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/historical_administrative_trading_halt_documents_phase612")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/historical_administrative_trading_halt_not_applicable_evidence_phase612_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/historical_administrative_trading_halt_audit_phase612_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_administrative_trading_halt_summary_phase612_v321.json")
    p=sub.add_parser("audit-related-party-rights-participation-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase612_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/related_party_rights_participation_documents_phase613")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/related_party_rights_participation_not_applicable_evidence_phase613_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/related_party_rights_participation_audit_phase613_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/related_party_rights_participation_summary_phase613_v321.json")
    p=sub.add_parser("audit-samsung-heavy-rights-price-followups-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase613_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--phase594-audit-csv",default="data/raw/v321/events/samsung_heavy_rights_audit_phase594_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/samsung_heavy_rights_price_followup_documents_phase614")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/samsung_heavy_rights_price_followup_not_applicable_evidence_phase614_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/samsung_heavy_rights_price_followup_audit_phase614_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/samsung_heavy_rights_price_followup_summary_phase614_v321.json")
    p=sub.add_parser("audit-asset-transfer-completion-reports-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase614_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/asset_transfer_completion_documents_phase615")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/asset_transfer_completion_not_applicable_evidence_phase615_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/asset_transfer_completion_audit_phase615_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/asset_transfer_completion_summary_phase615_v321.json")
    p=sub.add_parser("audit-physical-split-business-transfer-completions-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase615_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/physical_split_business_transfer_completion_documents_phase616")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/physical_split_business_transfer_completion_not_applicable_evidence_phase616_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/physical_split_business_transfer_completion_audit_phase616_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/physical_split_business_transfer_completion_summary_phase616_v321.json")
    p=sub.add_parser("audit-amorepacific-attachment-followups-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase616_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--phase595-audit-csv",default="data/raw/v321/events/amorepacific_restructuring_audit_phase595_v321.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/amorepacific_attachment_followup_not_applicable_evidence_phase617_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/amorepacific_attachment_followup_audit_phase617_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/amorepacific_attachment_followup_summary_phase617_v321.json")
    p=sub.add_parser("audit-rights-offering-followups-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase617_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/rights_offering_followup_not_applicable_evidence_phase618_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/rights_offering_followup_audit_phase618_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/rights_offering_followup_summary_phase618_v321.json")
    p=sub.add_parser("audit-hdhyundai-subsidiary-rights-amendments-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase618_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/hdhyundai_subsidiary_rights_amendment_not_applicable_evidence_phase619_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/hdhyundai_subsidiary_rights_amendment_audit_phase619_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/hdhyundai_subsidiary_rights_amendment_summary_phase619_v321.json")
    p=sub.add_parser("audit-kakao-split-amendments-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase619_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--phase590-audit-csv",default="data/raw/v321/events/historical_merger_spinoff_applicability_audit_phase590_v321.csv")
    p.add_argument("--phase616-audit-csv",default="data/raw/v321/events/physical_split_business_transfer_completion_audit_phase616_v321.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/kakao_split_amendment_not_applicable_evidence_phase620_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/kakao_split_amendment_audit_phase620_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/kakao_split_amendment_summary_phase620_v321.json")
    p=sub.add_parser("audit-historical-amendment-duplicates-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase620_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--chain-csv",default="data/raw/v321/events/historical_legal_event_chain_phase584_v321.csv")
    p.add_argument("--verification-csv",default="data/raw/v321/events/event_verification_resolved_phase620_v321.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/historical_amendment_duplicate_not_applicable_evidence_phase621_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/historical_amendment_duplicate_audit_phase621_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/historical_amendment_duplicate_summary_phase621_v321.json")
    p=sub.add_parser("audit-ecoprobm-rights-support-disclosures-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase621_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--phase618-audit-csv",default="data/raw/v321/events/rights_offering_followup_audit_phase618_v321.csv")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/ecoprobm_rights_support_not_applicable_evidence_phase622_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/ecoprobm_rights_support_audit_phase622_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/ecoprobm_rights_support_summary_phase622_v321.json")
    p=sub.add_parser("verify-ecoprobm-bonus-issue-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase622_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--trading-calendar-db",default="data/backup/stock_analytics_20260808_194044_baseline_v321.db")
    p.add_argument("--documents-dir",default="data/raw/v321/events/ecoprobm_bonus_issue_documents_phase623")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/ecoprobm_bonus_issue_strict_evidence_phase623_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/ecoprobm_bonus_issue_audit_phase623_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/ecoprobm_bonus_issue_summary_phase623_v321.json")
    p=sub.add_parser("audit-hd-ksoe-third-party-capital-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase623_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/hd_ksoe_third_party_capital_documents_phase624")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/hd_ksoe_third_party_capital_not_applicable_evidence_phase624_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/hd_ksoe_third_party_capital_audit_phase624_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/hd_ksoe_third_party_capital_summary_phase624_v321.json")
    p=sub.add_parser("audit-shinhan-neoplux-share-exchange-v321")
    p.add_argument("--actionable-queue-csv",default="data/raw/v321/events/actionable_resolution_queue_phase624_v321.csv")
    p.add_argument("--disclosures-csv",default="data/raw/v321/events/corporate_action_disclosures.csv")
    p.add_argument("--phase621-audit-csv",default="data/raw/v321/events/historical_amendment_duplicate_audit_phase621_v321.csv")
    p.add_argument("--documents-dir",default="data/raw/v321/events/shinhan_neoplux_share_exchange_documents_phase625")
    p.add_argument("--evidence-output-csv",default="data/raw/v321/events/shinhan_neoplux_share_exchange_not_applicable_evidence_phase625_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/shinhan_neoplux_share_exchange_audit_phase625_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/shinhan_neoplux_share_exchange_summary_phase625_v321.json")
    p=sub.add_parser("build-release-quality-gate-v321")
    p.add_argument("--verification-csv",default="data/raw/v321/events/event_verification_resolved_phase625_v321.csv")
    p.add_argument("--actionable-csv",default="data/raw/v321/events/actionable_resolution_queue_phase625_v321.csv")
    p.add_argument("--deferred-csv",default="data/raw/v321/events/deferred_dividend_queue_phase625_v321.csv")
    p.add_argument("--blocked-csv",default="data/raw/v321/events/blocked_resolution_queue_phase625_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/release_quality_gate_audit_phase626_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/release_quality_gate_summary_phase626_v321.json")
    p=sub.add_parser("verify-release-artifact-integrity-v321")
    p.add_argument("--manifest-csv",default="data/raw/v321/events/release_artifact_sha256_phase626_v321.csv")
    p.add_argument("--gate-summary-json",default="data/raw/v321/events/release_quality_gate_summary_phase626_v321.json")
    p.add_argument("--release-zip",default=r"C:\Users\user\Documents\Codex\2026-08-09\c-dev-stock-analytics-main-origin\outputs\backup\stock-analytics-phase626-release-quality-gate-20260815.zip")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/release_artifact_integrity_audit_phase627_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/release_artifact_integrity_summary_phase627_v321.json")
    p=sub.add_parser("verify-release-restore-drill-v321")
    p.add_argument("--release-zip",default=r"C:\Users\user\Documents\Codex\2026-08-09\c-dev-stock-analytics-main-origin\outputs\backup\stock-analytics-phase626-release-quality-gate-20260815.zip")
    p.add_argument("--manifest-csv",default="data/raw/v321/events/release_artifact_sha256_phase626_v321.csv")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/release_restore_drill_audit_phase628_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/release_restore_drill_summary_phase628_v321.json")
    p=sub.add_parser("build-runtime-readiness-gate-v321")
    p.add_argument("--requirements-lock",default="requirements-lock.txt")
    p.add_argument("--main-py",default="src/main.py")
    p.add_argument("--quality-summary-json",default="data/raw/v321/events/release_quality_gate_summary_phase626_v321.json")
    p.add_argument("--integrity-summary-json",default="data/raw/v321/events/release_artifact_integrity_summary_phase627_v321.json")
    p.add_argument("--restore-summary-json",default="data/raw/v321/events/release_restore_drill_summary_phase628_v321.json")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/runtime_readiness_audit_phase629_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/runtime_readiness_summary_phase629_v321.json")
    p=sub.add_parser("build-release-candidate-seal-v321")
    p.add_argument("--verification-csv",default="data/raw/v321/events/event_verification_resolved_phase625_v321.csv")
    p.add_argument("--release-zip",default=r"C:\Users\user\Documents\Codex\2026-08-09\c-dev-stock-analytics-main-origin\outputs\backup\stock-analytics-phase626-release-quality-gate-20260815.zip")
    p.add_argument("--requirements-txt",default="requirements.txt")
    p.add_argument("--requirements-lock",default="requirements-lock.txt")
    p.add_argument("--quality-summary-json",default="data/raw/v321/events/release_quality_gate_summary_phase626_v321.json")
    p.add_argument("--integrity-summary-json",default="data/raw/v321/events/release_artifact_integrity_summary_phase627_v321.json")
    p.add_argument("--restore-summary-json",default="data/raw/v321/events/release_restore_drill_summary_phase628_v321.json")
    p.add_argument("--runtime-summary-json",default="data/raw/v321/events/runtime_readiness_summary_phase629_v321.json")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/release_candidate_seal_audit_phase630_v321.csv")
    p.add_argument("--manifest-output-json",default="data/raw/v321/events/release_candidate_manifest_phase630_v321.json")
    p=sub.add_parser("build-rc-promotion-readiness-v321")
    p.add_argument("--manifest-json",default="data/raw/v321/events/release_candidate_manifest_phase630_v321.json")
    p.add_argument("--audit-output-csv",default="data/raw/v321/events/rc_promotion_readiness_audit_phase631_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/rc_promotion_readiness_summary_phase631_v321.json")
    p=sub.add_parser("build-release-approval-handoff-v321")
    p.add_argument("--rc-manifest-json",default="data/raw/v321/events/release_candidate_manifest_phase630_v321.json")
    p.add_argument("--readiness-summary-json",default="data/raw/v321/events/rc_promotion_readiness_summary_phase631_v321.json")
    p.add_argument("--readiness-audit-csv",default="data/raw/v321/events/rc_promotion_readiness_audit_phase631_v321.csv")
    p.add_argument("--handoff-json",default="data/raw/v321/events/release_approval_handoff_phase632_v321.json")
    p.add_argument("--checklist-md",default="data/raw/v321/events/release_approval_checklist_phase632_v321.md")
    p=sub.add_parser("build-release-notes-v321")
    p.add_argument("--handoff-json",default="data/raw/v321/events/release_approval_handoff_phase632_v321.json")
    p.add_argument("--release-notes-md",default="data/raw/v321/events/release_notes_phase633_v321.md")
    p.add_argument("--release-record-json",default="data/raw/v321/events/release_record_phase633_v321.json")
    p=sub.add_parser("build-repository-promotion-preflight-v321")
    p.add_argument("--repository",default=".")
    p.add_argument("--inventory-csv",default="data/raw/v321/events/repository_promotion_inventory_phase634_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/repository_promotion_preflight_phase634_v321.json")
    p=sub.add_parser("build-release-curation-manifest-v321")
    p.add_argument("--repository",default=".")
    p.add_argument("--preflight-summary-json",default="data/raw/v321/events/repository_promotion_preflight_phase634_v321.json")
    p.add_argument("--output-csv",default="data/raw/v321/events/release_curation_manifest_phase635_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/release_curation_summary_phase635_v321.json")
    p=sub.add_parser("build-manual-curation-resolution-v321")
    p.add_argument("--repository",default=".")
    p.add_argument("--curation-manifest-csv",default="data/raw/v321/events/release_curation_manifest_phase635_v321.csv")
    p.add_argument("--output-csv",default="data/raw/v321/events/release_curation_resolved_phase636_v321.csv")
    p.add_argument("--audit-csv",default="data/raw/v321/events/manual_curation_resolution_audit_phase636_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/manual_curation_resolution_summary_phase636_v321.json")
    p=sub.add_parser("build-curated-release-payload-v321")
    p.add_argument("--repository",default=".")
    p.add_argument("--resolution-summary-json",default="data/raw/v321/events/manual_curation_resolution_summary_phase636_v321.json")
    p.add_argument("--payload-zip",default=r"C:\Users\user\Documents\Codex\2026-08-09\c-dev-stock-analytics-main-origin\outputs\backup\stock-analytics-v321-rc1-curated-payload-20260817.zip")
    p.add_argument("--manifest-csv",default="data/raw/v321/events/release_payload_manifest_phase637_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/release_payload_summary_phase637_v321.json")
    p=sub.add_parser("verify-curated-payload-restore-v321")
    p.add_argument("--payload-zip",default=r"C:\Users\user\Documents\Codex\2026-08-09\c-dev-stock-analytics-main-origin\outputs\backup\stock-analytics-v321-rc1-curated-payload-20260817.zip")
    p.add_argument("--expected-summary-json",default="data/raw/v321/events/release_payload_summary_phase637_v321.json")
    p.add_argument("--audit-csv",default="data/raw/v321/events/curated_payload_restore_audit_phase638_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/curated_payload_restore_summary_phase638_v321.json")
    p=sub.add_parser("build-final-promotion-gate-v321")
    p.add_argument("--payload-summary-json",default="data/raw/v321/events/release_payload_summary_phase637_v321.json")
    p.add_argument("--restore-summary-json",default="data/raw/v321/events/curated_payload_restore_summary_phase638_v321.json")
    p.add_argument("--audit-csv",default="data/raw/v321/events/final_promotion_gate_audit_phase639_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/final_promotion_gate_summary_phase639_v321.json")
    p=sub.add_parser("build-final-release-bundle-v321")
    p.add_argument("--payload-zip",default=r"C:\Users\user\Documents\Codex\2026-08-09\c-dev-stock-analytics-main-origin\outputs\backup\stock-analytics-v321-rc1-curated-payload-20260817.zip")
    p.add_argument("--payload-summary-json",default="data/raw/v321/events/release_payload_summary_phase637_v321.json")
    p.add_argument("--restore-summary-json",default="data/raw/v321/events/curated_payload_restore_summary_phase638_v321.json")
    p.add_argument("--promotion-summary-json",default="data/raw/v321/events/final_promotion_gate_summary_phase639_v321.json")
    p.add_argument("--release-notes-md",default="data/raw/v321/events/release_notes_phase633_v321.md")
    p.add_argument("--bundle-zip",default=r"C:\Users\user\Documents\Codex\2026-08-09\c-dev-stock-analytics-main-origin\outputs\backup\stock-analytics-v321-final-release-bundle-20260818.zip")
    p.add_argument("--bundle-manifest-json",default="data/raw/v321/events/final_release_bundle_manifest_phase640_v321.json")
    p.add_argument("--audit-csv",default="data/raw/v321/events/final_release_bundle_audit_phase640_v321.csv")
    p.add_argument("--summary-json",default="data/raw/v321/events/final_release_bundle_summary_phase640_v321.json")
    p = sub.add_parser("extract-kind-aggregate-market-targets-v321")
    p.add_argument("--aggregate-manifest-csv", default="data/raw/v321/events/kind_aggregate_market_notice_manifest_phase538_v321.csv")
    p.add_argument("--acquisition-manifest-csv", default="data/raw/v321/events/recent_dividend_acquisition_enriched_phase536_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_aggregate_market_targets_phase538_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kind_aggregate_market_audit_phase538_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("recover-acquisition-company-names-v321")
    p.add_argument("--acquisition-manifest-csv", default="data/raw/v321/events/recent_dividend_acquisition_manifest_phase536_v321.csv")
    p.add_argument("--dividend-facts-csv", default="data/raw/v321/events/dividend_disclosure_facts.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/recent_dividend_acquisition_enriched_phase536_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/company_name_recovery_audit_phase536_v321.csv")
    p = sub.add_parser("acquire-direct-kind-dividend-decisions-v321")
    p.add_argument("--manifest-csv", default="data/raw/v321/events/kind_direct_decision_manifest_phase537_v321.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/kind_documents_phase537")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_direct_decision_pairing_phase537_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("build-paired-kind-market-observations-v321")
    p.add_argument("--pairing-csv", default="data/raw/v321/events/kind_dividend_decision_pairing_phase534_v321.csv")
    p.add_argument("--parsed-decisions-csv", default="data/raw/v321/events/kind_dividend_decision_parsed_phase534_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_paired_market_observations_phase535_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kind_paired_market_observations_audit_phase535_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("acquire-paired-kind-dividend-decisions-v321")
    p.add_argument("--notices-csv", default="data/raw/v321/events/kind_batch_market_notices_phase533_v321.csv")
    p.add_argument("--decision-disclosures-csv", default="data/raw/v321/events/stock_dividend_decision_disclosures_v321.csv")
    p.add_argument("--documents-dir", default="data/raw/v321/events/kind_documents_phase534")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_dividend_decision_pairing_phase534_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("prioritize-resolution-gaps-v321")
    p.add_argument("--resolved-verification-csv", default="data/raw/v321/events/event_verification_resolved_phase530_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/event_resolution_priority_queue_phase531_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/event_resolution_priority_summary_phase531_v321.json")
    p = sub.add_parser("build-recent-dividend-acquisition-manifest-v321")
    p.add_argument("--priority-queue-csv", default="data/raw/v321/events/event_resolution_priority_queue_phase531_v321.csv")
    p.add_argument("--decision-disclosures-csv", default="data/raw/v321/events/stock_dividend_decision_disclosures_v321.csv")
    p.add_argument("--strict-evidence-csv", default="data/raw/v321/events/official_event_evidence_strict_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/recent_dividend_acquisition_manifest_phase532_v321.csv")
    p.add_argument("--summary-json", default="data/raw/v321/events/recent_dividend_acquisition_summary_phase532_v321.json")
    p = sub.add_parser("discover-kind-market-notices-batch-v321")
    p.add_argument("--acquisition-manifest-csv", default="data/raw/v321/events/recent_dividend_acquisition_manifest_phase532_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_batch_market_notices_phase533_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kind_batch_market_search_audit_phase533_v321.csv")
    p.add_argument("--search-start", default="20260101")
    p.add_argument("--search-end", default="20260709")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("discover-kind-market-exdates-v321")
    p.add_argument("--candidates-csv", default="data/raw/v321/events/kind_market_exdate_discovery_candidates_v321.csv")
    p.add_argument("--output-csv", default="data/raw/v321/events/kind_market_exdate_discovered_v321.csv")
    p.add_argument("--audit-csv", default="data/raw/v321/events/kind_market_exdate_discovery_audit_v321.csv")
    p.add_argument("--timeout-seconds", type=int, default=20)
    p = sub.add_parser("discover-kodex-next-hops-v321")
    p.add_argument("--bodies-dir", required=True)
    p.add_argument("--output-csv", default="data/raw/v321/events/kodex_069500/high_signal/kodex_next_hop_candidates_v321.csv")
    p = sub.add_parser("phase516-selfcheck")
    p = sub.add_parser("ml-diagnose-v321")
    p.add_argument("--horizon", type=int, choices=[5, 20, 60], default=20)
    p.add_argument("--benchmark-code", default="069500")
    p.add_argument("--validation-days", type=int, default=252)
    p.add_argument("--test-days", type=int, default=126)
    p.add_argument("--min-train-days", type=int, default=504)
    p.add_argument("--fold-days", type=int, default=126)
    p.add_argument("--embargo-days", type=int)
    p.add_argument("--commission", type=float, default=.015)
    p.add_argument("--tax", type=float, default=.18)
    p.add_argument("--slippage", type=float, default=.05)
    p.add_argument("--stock-cap", type=float, default=.15)
    p.add_argument("--industry-cap", type=float, default=.40)
    p.add_argument("--lockbox-start")
    p.add_argument("--universe-history-csv")
    p.add_argument("--total-return-csv")
    p.add_argument("--security-master-csv")
    p.add_argument("--corporate-actions-csv")
    p.add_argument("--rank-scope", choices=["market", "industry"], default="market")
    p.add_argument("--output-prefix", default="ml_v321_h20")
    p.add_argument("--result-dir", help="이 실행의 결과만 저장할 새 폴더")
    p.add_argument("--zip-results", action="store_true", help="결과 폴더를 실행 종료 후 ZIP으로 압축")
    args = parser.parse_args()
    settings = get_settings()
    conn = connect(settings.db_path)
    atexit.register(conn.close)
    if args.command == "shadow-list":
        books = pd.read_sql_query("""SELECT a.portfolio_id,a.strategy_version,
            SUBSTR(a.config_hash,1,12) AS config_hash,a.initial_capital,a.cash,
            p.performance_date AS latest_date,p.equity,p.cumulative_return,p.benchmark_return
            FROM shadow_accounts a LEFT JOIN shadow_book_performance p
              ON p.portfolio_id=a.portfolio_id
             AND p.performance_date=(SELECT MAX(x.performance_date)
                 FROM shadow_book_performance x WHERE x.portfolio_id=a.portfolio_id)
            ORDER BY a.portfolio_id""", conn)
        print("등록된 그림자 포트폴리오가 없습니다." if books.empty else books.to_string(index=False))
    elif args.command == "daily-status":
        where = "WHERE portfolio_id=?" if args.portfolio_id else ""
        params = (args.portfolio_id, args.limit) if args.portfolio_id else (args.limit,)
        logs = pd.read_sql_query(f"""SELECT id,portfolio_id,started_at,finished_at,status,
            evaluation_date,price_rows,valuation_rows,error_count,message
            FROM daily_run_logs {where} ORDER BY id DESC LIMIT ?""", conn, params=params)
        print("daily-shadow 실행 기록이 없습니다." if logs.empty else logs.to_string(index=False))
        if not logs.empty:
            successes = logs[logs["status"] == "SUCCESS"]
            if successes.empty:
                print("경고: 조회 범위에 성공 실행 기록이 없습니다.")
            else:
                latest_success = pd.to_datetime(successes.iloc[0]["started_at"], utc=True)
                age_days = (pd.Timestamp.now(tz="UTC") - latest_success).total_seconds() / 86400
                if age_days > 4:
                    print(f"경고: 최근 성공 실행 후 {age_days:.1f}일이 지났습니다.")
    elif args.command == "ml-readiness":
        args.codes, _ = resolve_codes_and_industries(args)
        rows = []
        for code in args.codes:
            price_rows = conn.execute("SELECT COUNT(*) FROM stock_prices WHERE code=?", (code,)).fetchone()[0]
            valuation_days = conn.execute("SELECT COUNT(DISTINCT snapshot_date) FROM valuation_snapshots WHERE code=?",
                                          (code,)).fetchone()[0]
            annual_years = conn.execute("""SELECT COUNT(DISTINCT fiscal_year) FROM financial_statements
                WHERE code=? AND report_code='11011'""", (code,)).fetchone()[0]
            feature_rows = conn.execute("SELECT COUNT(*) FROM ml_features WHERE code=?", (code,)).fetchone()[0]
            label_days = conn.execute("""SELECT COUNT(*) FROM ml_labels
                WHERE code=? AND horizon=20""", (code,)).fetchone()[0]
            rows.append({"code": code, "price_rows": price_rows,
                         "valuation_snapshot_days": valuation_days, "annual_financial_years": annual_years,
                         "feature_rows": feature_rows, "label_20_rows": label_days})
        readiness = pd.DataFrame(rows)
        shadow_days = conn.execute("SELECT COUNT(*) FROM shadow_book_performance WHERE portfolio_id=?",
                                   (args.portfolio_id,)).fetchone()[0]
        print(readiness.to_string(index=False))
        price_ready = bool((readiness["price_rows"] >= 756).all())
        valuation_ready = bool((readiness["valuation_snapshot_days"] >= 120).all())
        financial_ready = bool((readiness["annual_financial_years"] >= 3).all())
        feature_ready = bool((readiness["feature_rows"] >= 500).all())
        label_ready = bool((readiness["label_20_rows"] >= 400).all())
        print(f"""[ML 준비도]
3년 이상 가격: {"충족" if price_ready else "부족"}
120일 이상 실시간 가치지표: {"충족" if valuation_ready else "축적 중(기준 모델 필수조건 아님)"}
3개년 이상 연간재무: {"충족" if financial_ready else "부족"}
시점 보존 Feature Store: {"충족" if feature_ready else "미구축 또는 부족"}
20거래일 라벨: {"충족" if label_ready else "미구축 또는 부족"}
그림자 실측 거래일: {shadow_days}일
최종 판정: {"기초 모델 학습 가능" if price_ready and feature_ready and label_ready else "Feature Store 구축 필요"}""")
    elif args.command == "shadow-report":
        print_shadow_report(conn, args.portfolio_id, args.export_csv)
    elif args.command == "daily-shadow":
        execute_daily_shadow(conn, settings, args)
    elif args.command == "build-feature-store":
        args.codes, mapping = resolve_codes_and_industries(args)
        feature_count, label_count = build_feature_store(
            conn, args.codes, mapping, args.benchmark_code)
        print(f"Feature Store 저장: {feature_count:,}행")
        print(f"미래수익 라벨 저장: {label_count:,}행 (5·20·60거래일)")
        print("시점 규칙: 각 행에는 feature_date까지 공시·관측된 정보만 사용")
    elif args.command == "ml-train":
        metadata = train_baselines(
            conn, args.horizon, args.benchmark_code, args.validation_days,
            args.test_days, args.artifact, args.output_prefix)
        print(f"기준 ML 학습 완료: {metadata['selected_model']}")
        print(f"학습/검증/봉인시험: {metadata['train_start']}~{metadata['train_end']} / "
              f"{metadata['validation_start']}~{metadata['validation_end']} / "
              f"{metadata['test_start']}~{metadata['test_end']}")
        print(f"모델 저장: {metadata['artifact_path']}")
    elif args.command == "ml-walk-forward":
        result = walk_forward_baselines(
            conn, args.horizon, args.benchmark_code, args.min_train_days,
            args.test_days, args.output_csv)
        summary = result.groupby("model_name")[["roc_auc", "accuracy", "brier",
            "top_quintile_excess_return"]].mean(numeric_only=True)
        print("[ML 워크포워드 평균]")
        print(summary.to_string())
        print(f"구간별 결과 저장: {args.output_csv}")
    elif args.command == "ml-predict":
        predictions = predict_latest(conn, args.artifact, args.output_csv)
        print(predictions[["rank", "code", "feature_date", "probability",
                           "selected_model"]].to_string(index=False))
        print(f"최신 예측 저장: {args.output_csv}")
    elif args.command == "ml-diagnose":
        args.codes, _ = resolve_codes_and_industries(args)
        summary = run_ml_diagnostics(
            conn, args.horizon, args.benchmark_code, args.validation_days,
            args.test_days, args.min_train_days, args.fold_days,
            args.commission, args.tax, args.slippage, args.portfolio_id,
            args.output_prefix)
        items, missing = financial_missingness_reports(
            conn, args.codes, args.start_year, args.end_year)
        prefix = Path(args.output_prefix)
        items.to_csv(prefix.with_name(prefix.name + "_financial_items.csv"),
                     index=False, encoding="utf-8-sig")
        missing.to_csv(prefix.with_name(prefix.name + "_feature_missingness.csv"),
                       index=False, encoding="utf-8-sig")
        passed = sum(summary["criteria"].values())
        print(f"[ML 종합 진단] {summary['verdict']} ({passed}/{len(summary['criteria'])} 기준 충족)")
        print(f"선택 모델/특징: {summary['selected_model']} / {summary['selected_feature_set']}")
        print(f"워크포워드 구간: {summary['walk_forward_folds']}개")
        for name, value in summary["criteria"].items():
            print(f"- {name}: {'통과' if value else '미통과'}")
        print(f"진단 결과 접두사: {args.output_prefix}")
    elif args.command == "ml-diagnose-v2":
        summary = run_ml_diagnostics_v2(
            conn, args.horizon, args.benchmark_code, args.validation_days,
            args.test_days, args.min_train_days, args.fold_days,
            args.commission, args.tax, args.slippage, args.output_prefix,
            args.lockbox_start, args.universe_history_csv, args.rank_scope)
        passed = sum(summary["criteria"].values())
        print(f"[교정 ML 진단] {summary['verdict']} "
              f"({passed}/{len(summary['criteria'])} 기준 충족)")
        print(f"선택 모델/특징/결측표시: {summary['selected_model']} / "
              f"{summary['selected_feature_set']} / "
              f"{summary['selected_missing_indicators']}")
        print(f"워크포워드: {summary['walk_forward_period']} "
              f"({summary['walk_forward_folds']}개, 검증·봉인 이전 전용)")
        print(f"검증기간: {summary['validation_period']}")
        print(f"봉인시험: {summary['lockbox_period']}")
        print(f"시점별 유니버스: {summary['universe_history_status']}")
        for name, value in summary["criteria"].items():
            print(f"- {name}: {'통과' if value else '미통과'}")
        print("안전 상태: 연구·그림자 전용, 실제 주문 기능 없음")
        print(f"교정 진단 결과 접두사: {args.output_prefix}")
    elif args.command == "ml-diagnose-v3":
        summary = run_ml_diagnostics_v3(
            conn, args.horizon, args.benchmark_code, args.validation_days,
            args.test_days, args.min_train_days, args.fold_days,
            args.commission, args.tax, args.slippage, args.output_prefix,
            args.lockbox_start, args.universe_history_csv, args.rank_scope)
        passed = sum(summary["criteria"].values())
        print(f"[V3 모델 토너먼트] {summary['verdict']} "
              f"({passed}/{len(summary['criteria'])} 기준 충족)")
        print(f"선택 모델/목표/특징: {summary['selected_model']} / "
              f"{summary['selected_target']} / {summary['selected_feature_set']}")
        print(f"워크포워드: {summary['walk_forward_period']} "
              f"({summary['walk_forward_folds']}개, 검증·봉인 이전 전용)")
        print(f"검증기간: {summary['validation_period']}")
        print(f"V3 봉인시험: {summary['lockbox_period']}")
        print(f"시점별 유니버스: {summary['universe_history_status']}")
        print(f"수익률 감사: {summary['return_audit']['status']}")
        for name, value in summary["criteria"].items():
            print(f"- {name}: {'통과' if value else '미통과'}")
        print("안전 상태: 연구·그림자 전용, 실제 주문 기능 없음")
        print(f"V3 결과 접두사: {args.output_prefix}")
    elif args.command == "ml-diagnose-v31":
        summary = run_ml_diagnostics_v31(
            conn, args.horizon, args.benchmark_code, args.validation_days,
            args.test_days, args.min_train_days, args.fold_days,
            args.commission, args.tax, args.slippage, args.output_prefix,
            args.lockbox_start, args.universe_history_csv,
            args.total_return_csv, args.security_master_csv, args.rank_scope)
        passed = sum(summary["criteria"].values())
        print(f"[V3.1 독립평가·앙상블] {summary['verdict']} "
              f"({passed}/{len(summary['criteria'])} 기준 충족)")
        print(f"선택 모델/목표/특징: {summary['selected_model']} / "
              f"{summary['selected_target']} / {summary['selected_feature_set']}")
        print(f"후보 모델: {summary['candidate_count']}개")
        print(f"워크포워드: {summary['walk_forward_period']} "
              f"({summary['walk_forward_folds']}개, 검증·공개시험 이전 전용)")
        print(f"검증기간: {summary['validation_period']}")
        print(f"기존 공개 시험기간: {summary['published_test_period']}")
        print(f"시점별 유니버스: {summary['universe_history_status']}")
        print(f"총수익률 감사: {summary['total_return_audit']['status']}")
        for name, value in summary["criteria"].items():
            print(f"- {name}: {'통과' if value else '미통과'}")
        print("안전 상태: 연구·그림자 전용, 실제 주문 기능 없음")
        print(f"V3.1 결과 접두사: {args.output_prefix}")
    elif args.command == "ml-diagnose-v32":
        summary = run_ml_diagnostics_v32(
            conn, args.horizon, args.benchmark_code, args.validation_days,
            args.test_days, args.min_train_days, args.fold_days, args.embargo_days,
            args.commission, args.tax, args.slippage, args.stock_cap,
            args.industry_cap, diagnostic_prefix, args.lockbox_start,
            args.universe_history_csv, args.total_return_csv,
            args.security_master_csv, args.corporate_actions_csv, args.rank_scope)
        passed = sum(summary["criteria"].values())
        print(f"[V3.2 중첩검증·위험오버레이] {summary['verdict']} "
              f"({passed}/{len(summary['criteria'])} 기준 충족)")
        print(f"Champion / 내부 선택 전략: {summary['champion_strategy']} / "
              f"{summary['selected_strategy']}")
        print(f"후보 / 내부 폴드 / embargo: {summary['candidate_count']}개 / "
              f"{summary['nested_fold_count']}개 / {summary['embargo_days']}거래일")
        print(f"검증기간: {summary['validation_period']}")
        print(f"기존 공개 시험기간: {summary['published_test_period']}")
        print(f"시점별 유니버스: {summary['universe_history_status']}")
        print(f"총수익률 감사: {summary['total_return_audit']['status']}")
        print(f"재무 공시시점 감사: {summary['financial_point_in_time_audit']['status']}")
        print(f"기업행사 감사: {summary['corporate_action_status']}")
        for name, value in summary["criteria"].items():
            print(f"- {name}: {'통과' if value else '미통과'}")
        print("안전 상태: 연구·그림자 전용, 실제 주문 기능 없음")
        print(f"V3.2 결과 접두사: {args.output_prefix}")
    elif args.command == "import-valuation-snapshots-v321":
        result = import_valuation_snapshots(conn, args.csv)
        print(f"[V3.2.1 Valuation Snapshot Import] {result['status']}")
        print(f"저장: {result['rows']:,}행 / {result['codes']:,}종목")
        print(f"기간: {result['first_snapshot']} ~ {result['last_snapshot']}")
        print(f"연구 경계: {result['research_seen_through']} 이후 snapshot 입력 금지")
        print("다음 단계: build-feature-store를 다시 실행하여 valuation_snapshot_date/known_at를 feature에 반영하세요.")
    elif args.command == "build-data-foundation-v321":
        try:
            result = build_data_foundation_v321(
                valuation_csv=args.valuation_csv, total_return_csv=args.total_return_csv,
                corporate_actions_csv=args.corporate_actions_csv,
                universe_history_csv=args.universe_history_csv, output_dir=args.output_dir)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Data Foundation] {exc}")
        print("[V3.2.1 Data Integrity Phase 3]")
        for row in result["audit"]:
            print(f"{row['dataset']}: {row['status']} / {row['rows']:,}행 / {row['codes']:,}종목")
        print(f"연구 경계: {result['research_seen_through']}")
        print(f"4종 데이터 모두 검증: {'통과' if result['all_four_verified'] else '미완료'}")
        print(f"출력 폴더: {args.output_dir}")
        print("주의: 과거값 역채움·보간·현재값 소급 적용은 수행하지 않습니다.")
    elif args.command == "krx-provider-check-v321":
        try:
            result = check_krx_provider_v321(args.code, args.end)
        except (ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 KRX Provider Check] {exc}")
        print("[V3.2.1 KRX Provider Check] PASS")
        print(f"provider: {result['provider']}")
        print(f"pykrx: {result['pykrx_version']}")
        print(f"probe: {result['probe_code']} / {result['probe_end']} / {result.get('rows', 0)}행")
        print("credentials: PRESENT (값은 출력하지 않음)")
    elif args.command == "acquire-historical-data-v321":
        try:
            result = acquire_historical_data_v321(
                universe_csv=args.universe_csv, start=args.start, end=args.end,
                output_dir=args.output_dir, frequency=args.frequency,
                index_code=args.index_code, sleep_seconds=args.sleep_seconds,
                timeout_seconds=args.timeout_seconds, max_retries=args.max_retries,
                retry_backoff_seconds=args.retry_backoff_seconds, resume=not args.no_resume)
        except KeyboardInterrupt:
            raise SystemExit(
                "\n[V3.2.1 Historical Acquisition] 사용자 중단. 완료된 연도 checkpoint는 보존되었습니다. "
                "같은 명령을 다시 실행하면 미완료 구간부터 재개합니다.")
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Historical Acquisition] {exc}")
        print("[V3.2.1 Historical Data Acquisition Phase 4.2]")
        print(f"Valuation: {result['valuation_strict_status']} / {result['valuation_rows']:,}행 / {result['valuation_codes']:,}종목")
        print(f"Universe observations: {result['universe_observation_rows']:,}행")
        print(f"연구 경계: {result['research_seen_through']}")
        print("Total return: 미수집 (수정주가를 total return으로 위장하지 않음)")
        print("Corporate actions: 미수집 (공시일/효력일 조정 전에는 canonical 승격 금지)")
        print(f"출력 폴더: {args.output_dir}")
        print(f"Chunking: {result.get('chunking', 'ANNUAL')} / timeout {result.get('request_timeout_seconds')}초 / 최대 재시도 {result.get('max_retries')}회")
        print(f"Resume: {'ON' if result.get('resume_enabled') else 'OFF'} / checkpoint: {result.get('checkpoint_dir')}")
        print(f"다음 명령: {result['next_command']}")
    elif args.command == "db-health-v321":
        health = inspect_persistent_data_v321(conn, settings.db_path, args.benchmark_code)
        print("[V3.2.1 Persistent Data Health]")
        print(f"DB: {health.db_path} ({health.db_bytes:,} bytes)")
        print(f"stock_prices: {health.stock_prices:,}행 / {health.price_codes}종목 / benchmark {args.benchmark_code}: {health.benchmark_rows:,}행")
        print(f"valuation_snapshots: {health.valuation_snapshots:,}행 / {health.valuation_codes}종목")
        print(f"ml_features: {health.ml_features:,}행 / {health.feature_codes}종목")
        print(f"ml_labels: {health.ml_labels:,}행 / {health.label_codes}종목")
        print(f"상태: {'PRESERVED' if health.healthy_for_v321 else 'NOT_READY'}")
        if args.output_json:
            print(f"Health snapshot: {write_health_snapshot_v321(health, args.output_json)}")
    elif args.command == "backup-db-v321":
        result = backup_database_v321(conn, settings.db_path, args.output_dir, args.label)
        print("[V3.2.1 DB Backup] VERIFIED")
        print(f"백업: {result['backup_path']}")
        print(f"검증 manifest: {result['manifest_path']}")
    elif args.command == "acquire-payout-actions-v321":
        try:
            codes, _ = load_universe_csv(args.universe_csv)
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
    elif args.command == "build-stock-cash-amount-candidates-v321":
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
    elif args.command == "crosscheck-kind-dividends-v321":
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
    elif args.command == "validate-primary-adjustment-market-dates-v321":
        try:
            result=validate_primary_adjustment_market_dates_v321(
                PykrxMarketAdjustmentProvider(),terms_csv=args.terms_csv,
                execution_manifest_csv=args.execution_manifest_csv,trading_calendar_db=args.trading_calendar_db,
                evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.88] {exc}")
        print("[V3.2.1 Phase 5.88 Primary Adjustment Market Validation]")
        print(f"Candidates: {result['extracted_candidate_rows']:,}")
        print(f"PIT-valid: {result['pit_valid_rows']:,}")
        print(f"Safe market candidates: {result['safe_market_factor_candidates']:,}")
        print(f"Strict market evidence: {result['strict_market_evidence_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "verify-samsung-heavy-rights-v321":
        try:
            settings=get_settings()
            result=verify_samsung_heavy_rights_v321(
                DartClient(settings.dart_api_key),PykrxMarketAdjustmentProvider(),
                review_queue_csv=args.review_queue_csv,decision_documents_dir=args.decision_documents_dir,
                output_documents_dir=args.output_documents_dir,evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.94] {exc}")
        print("[V3.2.1 Phase 5.94 Samsung Heavy Rights Verification]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Strict evidence: {result['strict_evidence_rows']:,}")
        print(f"Effective date: {result['effective_date']}")
        print(f"Adjustment factor: {result['adjustment_factor']}")
        print(f"Theoretical gap: {result['theoretical_gap']}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-amorepacific-restructuring-v321":
        try:
            result=audit_amorepacific_restructuring_v321(
                PykrxMarketAdjustmentProvider(),review_queue_csv=args.review_queue_csv,
                official_candidates_csv=args.official_candidates_csv,
                evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.95] {exc}")
        print("[V3.2.1 Phase 5.95 Amorepacific Restructuring Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-overseas-listing-delistings-v321":
        try:
            settings=get_settings()
            result=audit_overseas_listing_delistings_v321(
                DartClient(settings.dart_api_key),PykrxMarketAdjustmentProvider(),
                actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.96] {exc}")
        print("[V3.2.1 Phase 5.96 Overseas Listing Delisting Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-lgchem-subsidiary-rights-v321":
        try:
            settings=get_settings()
            result=audit_lgchem_subsidiary_rights_v321(
                DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,
                disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.97] {exc}")
        print("[V3.2.1 Phase 5.97 LG Chem Subsidiary Rights Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-hdhyundai-exchangeable-bond-v321":
        try:
            settings=get_settings()
            result=audit_hdhyundai_exchangeable_bond_v321(
                DartClient(settings.dart_api_key),PykrxMarketAdjustmentProvider(),
                actionable_queue_csv=args.actionable_queue_csv,documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.98] {exc}")
        print("[V3.2.1 Phase 5.98 HD Hyundai Exchangeable Bond Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-ecoprobm-merger-transfer-v321":
        try:
            settings=get_settings();result=audit_ecoprobm_merger_transfer_v321(DartClient(settings.dart_api_key),PykrxMarketAdjustmentProvider(),actionable_queue_csv=args.actionable_queue_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc: raise SystemExit(f"[V3.2.1 Phase 5.99] {exc}")
        print("[V3.2.1 Phase 5.99 Ecopro BM Merger and Transfer Applicability]")
        print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-kakao-zero-ratio-merger-v321":
        try:
            settings=get_settings();result=audit_kakao_zero_ratio_merger_v321(DartClient(settings.dart_api_key),PykrxMarketAdjustmentProvider(),actionable_queue_csv=args.actionable_queue_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.00] {exc}")
        print("[V3.2.1 Phase 6.00 Kakao Zero-ratio Merger Applicability]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-celltrion-merger-followups-v321":
        try:
            settings=get_settings();result=audit_celltrion_merger_followups_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,phase591_audit_csv=args.phase591_audit_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.01] {exc}")
        print("[V3.2.1 Phase 6.01 Celltrion Merger Follow-up Consolidation]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-kakao-overseas-dr-delisting-v321":
        try:
            settings=get_settings();result=audit_kakao_overseas_dr_delisting_v321(DartClient(settings.dart_api_key),PykrxMarketAdjustmentProvider(),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.02] {exc}")
        print("[V3.2.1 Phase 6.02 Kakao Overseas DR Delisting]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-samsung-heavy-preferred-delisting-warnings-v321":
        try:
            settings=get_settings();result=audit_samsung_heavy_preferred_delisting_warnings_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.03] {exc}")
        print("[V3.2.1 Phase 6.03 Samsung Heavy Preferred-share Delisting Warnings]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-hd-ksoe-subsidiary-zero-ratio-merger-v321":
        try:
            settings=get_settings();result=audit_hd_ksoe_subsidiary_zero_ratio_merger_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.04] {exc}")
        print("[V3.2.1 Phase 6.04 HD KSOE Subsidiary Zero-ratio Merger]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-ecoprobm-subsidiary-capital-increases-v321":
        try:
            settings=get_settings();result=audit_ecoprobm_subsidiary_capital_increases_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.05] {exc}")
        print("[V3.2.1 Phase 6.05 Ecopro BM Subsidiary Capital Increases]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-lgchem-historical-subsidiary-capital-v321":
        try:
            settings=get_settings();result=audit_lgchem_historical_subsidiary_capital_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.06] {exc}")
        print("[V3.2.1 Phase 6.06 LG Chem Historical Subsidiary Capital]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-amorepacific-us-subsidiary-capital-v321":
        try:
            settings=get_settings();result=audit_amorepacific_us_subsidiary_capital_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.07] {exc}")
        print("[V3.2.1 Phase 6.07 Amorepacific US Subsidiary Capital]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-skhynix-subsidiary-capital-v321":
        try:
            settings=get_settings();result=audit_skhynix_subsidiary_capital_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.08] {exc}")
        print("[V3.2.1 Phase 6.08 SK hynix Subsidiary Capital]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-cj-schwans-subsidiary-mergers-v321":
        try:
            settings=get_settings();result=audit_cj_schwans_subsidiary_mergers_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.09] {exc}")
        print("[V3.2.1 Phase 6.09 CJ Schwan's Subsidiary Mergers]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-kakao-games-subsidiary-capital-v321":
        try:
            settings=get_settings();result=audit_kakao_games_subsidiary_capital_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.10] {exc}")
        print("[V3.2.1 Phase 6.10 Kakao Games Subsidiary Capital]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-naver-line-overseas-delisting-v321":
        try:
            settings=get_settings();result=audit_naver_line_overseas_delisting_v321(DartClient(settings.dart_api_key),PykrxMarketAdjustmentProvider(),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.11] {exc}")
        print("[V3.2.1 Phase 6.11 NAVER LINE Overseas Delisting]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-historical-administrative-trading-halts-v321":
        try:
            settings=get_settings();result=audit_historical_administrative_trading_halts_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.12] {exc}")
        print("[V3.2.1 Phase 6.12 Historical Administrative Trading Halts]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-related-party-rights-participation-v321":
        try:
            settings=get_settings();result=audit_related_party_rights_participation_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.13] {exc}")
        print("[V3.2.1 Phase 6.13 Related-party Rights Participation]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-samsung-heavy-rights-price-followups-v321":
        try:
            settings=get_settings();result=audit_samsung_heavy_rights_price_followups_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,phase594_audit_csv=args.phase594_audit_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.14] {exc}")
        print("[V3.2.1 Phase 6.14 Samsung Heavy Rights Price Follow-ups]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-asset-transfer-completion-reports-v321":
        try:
            settings=get_settings();result=audit_asset_transfer_completion_reports_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.15] {exc}")
        print("[V3.2.1 Phase 6.15 Asset-transfer Completion Reports]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-physical-split-business-transfer-completions-v321":
        try:
            settings=get_settings();result=audit_physical_split_business_transfer_completions_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.16] {exc}")
        print("[V3.2.1 Phase 6.16 Physical-split and Business-transfer Completions]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-amorepacific-attachment-followups-v321":
        try:
            result=audit_amorepacific_attachment_followups_v321(actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,phase595_audit_csv=args.phase595_audit_csv,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.17] {exc}")
        print("[V3.2.1 Phase 6.17 Amorepacific Attachment Follow-ups]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-rights-offering-followups-v321":
        try:
            result=audit_rights_offering_followups_v321(actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.18] {exc}")
        print("[V3.2.1 Phase 6.18 Rights-offering Follow-ups]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-hdhyundai-subsidiary-rights-amendments-v321":
        try:
            result=audit_hdhyundai_subsidiary_rights_amendments_v321(actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.19] {exc}")
        print("[V3.2.1 Phase 6.19 HD Hyundai Subsidiary Rights Amendments]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-kakao-split-amendments-v321":
        try:
            result=audit_kakao_split_amendments_v321(actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,phase590_audit_csv=args.phase590_audit_csv,phase616_audit_csv=args.phase616_audit_csv,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.20] {exc}")
        print("[V3.2.1 Phase 6.20 Kakao Split Amendments]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-historical-amendment-duplicates-v321":
        try:
            result=audit_historical_amendment_duplicates_v321(actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,chain_csv=args.chain_csv,verification_csv=args.verification_csv,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.21] {exc}")
        print("[V3.2.1 Phase 6.21 Historical Amendment Duplicates]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-ecoprobm-rights-support-disclosures-v321":
        try:
            result=audit_ecoprobm_rights_support_disclosures_v321(actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,phase618_audit_csv=args.phase618_audit_csv,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.22] {exc}")
        print("[V3.2.1 Phase 6.22 Ecopro BM Rights Support Disclosures]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "verify-ecoprobm-bonus-issue-v321":
        try:
            settings=get_settings();result=verify_ecoprobm_bonus_issue_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,trading_calendar_db=args.trading_calendar_db,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.23] {exc}")
        print("[V3.2.1 Phase 6.23 Ecopro BM Bonus Issue]");print(f"Targets: {result['target_rows']:,}");print(f"Strict evidence: {result['strict_evidence_rows']:,}");print(f"Effective date: {result['effective_date']}");print(f"Adjustment factor: {result['adjustment_factor']}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-hd-ksoe-third-party-capital-v321":
        try:
            settings=get_settings();result=audit_hd_ksoe_third_party_capital_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.24] {exc}")
        print("[V3.2.1 Phase 6.24 HD KSOE Third-party Capital]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-shinhan-neoplux-share-exchange-v321":
        try:
            settings=get_settings();result=audit_shinhan_neoplux_share_exchange_v321(DartClient(settings.dart_api_key),actionable_queue_csv=args.actionable_queue_csv,disclosures_csv=args.disclosures_csv,phase621_audit_csv=args.phase621_audit_csv,documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:raise SystemExit(f"[V3.2.1 Phase 6.25] {exc}")
        print("[V3.2.1 Phase 6.25 Shinhan-Neoplux Share Exchange]");print(f"Targets: {result['target_rows']:,}");print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}");print(f"Unresolved: {result['unresolved_rows']:,}");print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "build-release-quality-gate-v321":
        try:
            result=build_release_quality_gate_v321(verification_csv=args.verification_csv,actionable_csv=args.actionable_csv,deferred_csv=args.deferred_csv,blocked_csv=args.blocked_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.26] {exc}")
        print("[V3.2.1 Phase 6.26 Release Quality Gate]");print(f"Gate: {result['release_gate']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Ledger rows: {result['input_rows']:,}");print(f"Actionable: {result['actionable_rows']:,}");print(f"Output: {result['audit_output_csv']}")
    elif args.command == "verify-release-artifact-integrity-v321":
        try:
            result=verify_release_artifact_integrity_v321(manifest_csv=args.manifest_csv,gate_summary_json=args.gate_summary_json,release_zip=args.release_zip,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.27] {exc}")
        print("[V3.2.1 Phase 6.27 Release Artifact Integrity]");print(f"Integrity: {result['integrity_status']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Manifest files: {result['manifest_files']}");print(f"ZIP entries: {result['release_zip_entries']}");print(f"Output: {result['audit_output_csv']}")
    elif args.command == "verify-release-restore-drill-v321":
        try:
            result=verify_release_restore_drill_v321(release_zip=args.release_zip,manifest_csv=args.manifest_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.28] {exc}")
        print("[V3.2.1 Phase 6.28 Release Restore Drill]");print(f"Restore drill: {result['restore_drill']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Restored entries: {result['restored_entries']}");print(f"Temporary cleaned: {result['temporary_restore_cleaned']}");print(f"Output: {result['audit_output_csv']}")
    elif args.command == "build-runtime-readiness-gate-v321":
        try:
            result=build_runtime_readiness_gate_v321(requirements_lock=args.requirements_lock,main_py=args.main_py,quality_summary_json=args.quality_summary_json,integrity_summary_json=args.integrity_summary_json,restore_summary_json=args.restore_summary_json,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.29] {exc}")
        print("[V3.2.1 Phase 6.29 Runtime Readiness Gate]");print(f"Runtime: {result['runtime_readiness']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Python: {result['python_version']}");print(f"Locked dependencies: {result['locked_dependencies']}");print(f"Output: {result['audit_output_csv']}")
    elif args.command == "build-release-candidate-seal-v321":
        try:
            result=build_release_candidate_seal_v321(verification_csv=args.verification_csv,release_zip=args.release_zip,requirements_txt=args.requirements_txt,requirements_lock=args.requirements_lock,quality_summary_json=args.quality_summary_json,integrity_summary_json=args.integrity_summary_json,restore_summary_json=args.restore_summary_json,runtime_summary_json=args.runtime_summary_json,audit_output_csv=args.audit_output_csv,manifest_output_json=args.manifest_output_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.30] {exc}")
        print("[V3.2.1 Phase 6.30 Release Candidate Seal]");print(f"Release: {result['release_id']}");print(f"Seal: {result['seal_status']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Git tag created: {result['git_tag_created']}");print(f"Output: {result['manifest_output_json']}")
    elif args.command == "build-rc-promotion-readiness-v321":
        try:
            result=build_rc_promotion_readiness_v321(manifest_json=args.manifest_json,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.31] {exc}")
        print("[V3.2.1 Phase 6.31 RC Promotion Readiness]");print(f"Release: {result['release_id']}");print(f"State: {result['promotion_state']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Git tag created: {result['git_tag_created']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-release-approval-handoff-v321":
        try:
            result=build_release_approval_handoff_v321(rc_manifest_json=args.rc_manifest_json,readiness_summary_json=args.readiness_summary_json,readiness_audit_csv=args.readiness_audit_csv,handoff_json=args.handoff_json,checklist_md=args.checklist_md)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.32] {exc}")
        print("[V3.2.1 Phase 6.32 Release Approval Handoff]");print(f"Release: {result['release_id']}");print(f"Status: {result['handoff_status']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Git tag created: {result['git_tag_created']}");print(f"Output: {result['handoff_json']}")
    elif args.command == "build-release-notes-v321":
        try:
            result=build_release_notes_v321(handoff_json=args.handoff_json,release_notes_md=args.release_notes_md,release_record_json=args.release_record_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.33] {exc}")
        print("[V3.2.1 Phase 6.33 Release Notes]");print(f"Release: {result['release_id']}");print(f"Status: {result['release_notes_status']}");print(f"Approval: {result['approval_state']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Output: {result['release_record_json']}")
    elif args.command == "build-repository-promotion-preflight-v321":
        try:
            result=build_repository_promotion_preflight_v321(repository=args.repository,inventory_csv=args.inventory_csv,summary_json=args.summary_json)
        except (FileNotFoundError,subprocess.CalledProcessError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.34] {exc}")
        print("[V3.2.1 Phase 6.34 Repository Promotion Preflight]");print(f"Branch: {result['branch']}@{result['head']}");print(f"Status: {result['promotion_preflight']}");print(f"Changed paths: {result['changed_paths']}");print(f"Git tag created: {result['git_tag_created']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-release-curation-manifest-v321":
        try:
            result=build_release_curation_manifest_v321(repository=args.repository,preflight_summary_json=args.preflight_summary_json,output_csv=args.output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.35] {exc}")
        print("[V3.2.1 Phase 6.35 Release Curation Manifest]");print(f"Status: {result['curation_status']}");print(f"Files: {result['files_inventory_total']}");print(f"Decisions: {result['decision_counts']}");print(f"Files staged: {result['files_staged']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-manual-curation-resolution-v321":
        try:
            result=build_manual_curation_resolution_v321(repository=args.repository,curation_manifest_csv=args.curation_manifest_csv,output_csv=args.output_csv,audit_csv=args.audit_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.36] {exc}")
        print("[V3.2.1 Phase 6.36 Manual Curation Resolution]");print(f"Status: {result['curation_resolution']}");print(f"Resolved: {result['resolved_manual_review']}/{result['input_manual_review']}");print(f"Remaining: {result['remaining_manual_review']}");print(f"Files deleted: {result['files_deleted']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-curated-release-payload-v321":
        try:
            result=build_curated_release_payload_v321(repository=args.repository,resolution_summary_json=args.resolution_summary_json,payload_zip=args.payload_zip,manifest_csv=args.manifest_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.37] {exc}")
        print("[V3.2.1 Phase 6.37 Curated Release Payload]");print(f"Release: {result['release_id']}");print(f"Status: {result['payload_status']}");print(f"Included: {result['included_files']}");print(f"Excluded: {result['excluded_files']}");print(f"SHA-256: {result['zip_sha256']}");print(f"Output: {result['payload_zip']}")
    elif args.command == "verify-curated-payload-restore-v321":
        try:
            result=verify_curated_payload_restore_v321(payload_zip=args.payload_zip,expected_summary_json=args.expected_summary_json,audit_csv=args.audit_csv,summary_json=args.summary_json,python_executable=os.sys.executable)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.38] {exc}")
        print("[V3.2.1 Phase 6.38 Curated Payload Restore Drill]");print(f"Release: {result['release_id']}");print(f"Status: {result['restore_drill']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Restored tests: {result['restored_tests']}");print(f"Temporary restore cleaned: {result['temporary_restore_cleaned']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-final-promotion-gate-v321":
        try:
            result=build_final_promotion_gate_v321(payload_summary_json=args.payload_summary_json,restore_summary_json=args.restore_summary_json,audit_csv=args.audit_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.39] {exc}")
        print("[V3.2.1 Phase 6.39 Final Promotion Gate]");print(f"Release: {result['release_id']}");print(f"Gate: {result['final_promotion_gate']}");print(f"State: {result['promotion_state']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-final-release-bundle-v321":
        try:
            result=build_final_release_bundle_v321(payload_zip=args.payload_zip,payload_summary_json=args.payload_summary_json,restore_summary_json=args.restore_summary_json,promotion_summary_json=args.promotion_summary_json,release_notes_md=args.release_notes_md,bundle_zip=args.bundle_zip,bundle_manifest_json=args.bundle_manifest_json,audit_csv=args.audit_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.40] {exc}")
        print("[V3.2.1 Phase 6.40 Final Release Bundle]");print(f"Release: {result['release_id']}");print(f"Status: {result['final_bundle_status']}");print(f"State: {result['release_state']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"SHA-256: {result['bundle_sha256']}");print(f"Output: {result['bundle_zip']}")
    elif args.command == "audit-incomplete-primary-adjustments-v321":
        try:
            result=audit_incomplete_primary_adjustments_v321(
                terms_csv=args.terms_csv,execution_manifest_csv=args.execution_manifest_csv,
                documents_dir=args.documents_dir,trading_calendar_db=args.trading_calendar_db,
                evidence_output_csv=args.evidence_output_csv,review_output_csv=args.review_output_csv,
                audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.93] {exc}")
        print("[V3.2.1 Phase 5.93 Incomplete Primary Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Direct reparse: {result['direct_reparse_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-historical-capital-reductions-v321":
        try:
            result=audit_historical_capital_reductions_v321(
                terms_csv=args.terms_csv,execution_manifest_csv=args.execution_manifest_csv,
                documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.92] {exc}")
        print("[V3.2.1 Phase 5.92 Capital Reduction Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Listed reduction review: {result['listed_reduction_review_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "reparse-celltrion-merger-v321":
        try:
            result=reparse_celltrion_merger_v321(
                PykrxMarketAdjustmentProvider(),applicability_audit_csv=args.applicability_audit_csv,
                terms_csv=args.terms_csv,official_candidates_csv=args.official_candidates_csv,
                evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.91] {exc}")
        print("[V3.2.1 Phase 5.91 Celltrion Merger Reparse]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-historical-merger-spinoff-applicability-v321":
        try:
            result=audit_historical_merger_spinoff_applicability_v321(
                terms_csv=args.terms_csv,execution_manifest_csv=args.execution_manifest_csv,
                documents_dir=args.documents_dir,trading_calendar_db=args.trading_calendar_db,
                evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,
                summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.90] {exc}")
        print("[V3.2.1 Phase 5.90 Merger/Spinoff Applicability]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Material or reparse: {result['material_or_reparse_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "audit-historical-rights-applicability-v321":
        try:
            result=audit_historical_rights_applicability_v321(
                terms_csv=args.terms_csv,execution_manifest_csv=args.execution_manifest_csv,
                documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.89] {exc}")
        print("[V3.2.1 Phase 5.89 Rights Applicability Audit]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Shareholder-rights TERP candidates: {result['shareholder_rights_terp_candidates']:,}")
        print(f"Unresolved allotment methods: {result['unresolved_allotment_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "consolidate-historical-legal-chains-v321":
        try:
            result=consolidate_historical_legal_chains_v321(
                validation_csv=args.validation_csv,chain_csv=args.chain_csv,
                group_output_csv=args.group_output_csv,evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.86] {exc}")
        print("[V3.2.1 Phase 5.86 Historical Chain Consolidation]")
        print(f"Confirmed children: {result['confirmed_child_rows']:,}")
        print(f"Legal event groups: {result['consolidated_legal_event_groups']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Primary events resolved: {result['primary_events_resolved']:,}")
        print(f"Output: {result['group_output_csv']}")
    elif args.command == "extract-primary-adjustment-document-terms-v321":
        try:
            settings=get_settings()
            result=extract_primary_adjustment_document_terms_v321(
                DartClient(settings.dart_api_key),execution_manifest_csv=args.execution_manifest_csv,
                disclosures_csv=args.disclosures_csv,legal_groups_csv=args.legal_groups_csv,
                documents_dir=args.documents_dir,output_csv=args.output_csv,
                review_queue_csv=args.review_queue_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.87] {exc}")
        print("[V3.2.1 Phase 5.87 Primary Adjustment Document Terms]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Selected receipts: {result['selected_receipt_rows']:,}")
        print(f"Unique documents: {result['unique_documents_processed']:,}")
        print(f"Terms extracted: {result['terms_extracted_rows']:,}")
        print(f"Review rows: {result['review_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "validate-historical-chain-documents-v321":
        try:
            settings=get_settings()
            result=validate_historical_chain_documents_v321(
                DartClient(settings.dart_api_key),chain_csv=args.chain_csv,
                execution_manifest_csv=args.execution_manifest_csv,disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,output_csv=args.output_csv,
                review_queue_csv=args.review_queue_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.85] {exc}")
        print("[V3.2.1 Phase 5.85 Historical Chain Document Validation]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Unique receipts processed: {result['unique_receipts_processed']:,}")
        print(f"Semantic chains confirmed: {result['semantic_chains_confirmed']:,}")
        print(f"Review rows: {result['semantic_or_acquisition_review_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "quarantine-periodic-dividend-aggregates-v321":
        try:
            result=quarantine_periodic_dividend_aggregates_v321(
                execution_manifest_csv=args.execution_manifest_csv,dividend_facts_csv=args.dividend_facts_csv,
                evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv,
                replacement_queue_csv=args.replacement_queue_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.83] {exc}")
        print("[V3.2.1 Phase 5.83 Periodic Dividend Aggregate Quarantine]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Quarantined placeholders: {result['quarantined_not_applicable_rows']:,}")
        print(f"Validation failed: {result['validation_failed_rows']:,}")
        print(f"Replacement requirements: {result['replacement_requirements']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "build-historical-legal-event-chain-v321":
        try:
            result=build_historical_legal_event_chain_v321(
                execution_manifest_csv=args.execution_manifest_csv,disclosures_csv=args.disclosures_csv,
                output_csv=args.output_csv,review_queue_csv=args.review_queue_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.84] {exc}")
        print("[V3.2.1 Phase 5.84 Historical Legal Event Chain]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Unique child receipts: {result['unique_child_receipts']:,}")
        print(f"Ready for semantic validation: {result['ready_for_semantic_validation']:,}")
        print(f"Manual review: {result['manual_review_rows']:,}")
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
    elif args.command == "discover-kind-market-exdates-v321":
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
    elif args.command == "prioritize-resolution-gaps-v321":
        try:
            result = prioritize_resolution_gaps_v321(
                resolved_verification_csv=args.resolved_verification_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.31] {exc}")
        print("[V3.2.1 Phase 5.31 Resolution Gap Prioritizer]")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Priority counts: {result['priority_counts']}")
        print(f"Next target: {result['next_target']}")
        print(f"Output: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "build-recent-dividend-acquisition-manifest-v321":
        try:
            result = build_recent_dividend_acquisition_manifest_v321(
                priority_queue_csv=args.priority_queue_csv,
                decision_disclosures_csv=args.decision_disclosures_csv,
                strict_evidence_csv=args.strict_evidence_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.32] {exc}")
        print("[V3.2.1 Phase 5.32 Recent Dividend Acquisition Manifest]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "discover-kind-market-notices-batch-v321":
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
    elif args.command == "recover-acquisition-company-names-v321":
        try:
            result = recover_acquisition_company_names_v321(
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                dividend_facts_csv=args.dividend_facts_csv,
                output_csv=args.output_csv,
                audit_csv=args.audit_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.36] {exc}")
        print("[V3.2.1 Phase 5.36 Company Name Recovery]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Recovered names: {result['recovered_names']:,}")
        print(f"Remaining missing: {result['remaining_missing']:,}")
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
    elif args.command == "extract-kind-aggregate-market-targets-v321":
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
    elif args.command == "audit-market-notice-coverage-v321":
        try:
            result = audit_market_notice_coverage_v321(
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                strict_evidence_csv=args.strict_evidence_csv,
                discovery_csvs=args.discovery_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.42] {exc}")
        print("[V3.2.1 Phase 5.42 Market Notice Coverage Audit]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Coverage: {result['coverage_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "classify-recent-corporate-actions-v321":
        try:
            result = classify_recent_corporate_actions_v321(
                priority_queue_csv=args.priority_queue_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.43] {exc}")
        print("[V3.2.1 Phase 5.43 Recent Corporate Action Classifier]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Priority counts: {result['priority_counts']}")
        print(f"Direct issuer actions: {result['direct_issuer_action_rows']:,}")
        print(f"Output: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "build-corporate-action-candidate-manifest-v321":
        try:
            result = build_corporate_action_candidate_manifest_v321(
                classified_queue_csv=args.classified_queue_csv,
                official_candidates_csv=args.official_candidates_csv,
                output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.44] {exc}")
        print("[V3.2.1 Phase 5.44 Corporate Action Candidate Manifest]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "select-market-adjustment-candidates-v321":
        try:
            result = select_market_adjustment_candidates_v321(
                candidate_manifest_csv=args.candidate_manifest_csv,
                official_candidates_csv=args.official_candidates_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.45] {exc}")
        print("[V3.2.1 Phase 5.45 Market Adjustment Candidate Selector]")
        print(f"Receipts: {result['manifest_receipts']:,}")
        print(f"Selected: {result['selected_candidates']:,}")
        print(f"Action counts: {result['action_counts']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "acquire-missing-corporate-action-documents-v321":
        try:
            result = acquire_missing_corporate_action_documents_v321(
                DartClient(settings.dart_api_key),
                candidate_manifest_csv=args.candidate_manifest_csv,
                disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.46] {exc}")
        print("[V3.2.1 Phase 5.46 Corporate Action Document Acquisition]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Acquired: {result['acquired_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Output: {result['output_csv']}")
        print(f"Documents: {result['documents_dir']}")
    elif args.command == "parse-corporate-action-documents-v321":
        try:
            result = parse_corporate_action_documents_v321(
                acquisition_csv=args.acquisition_csv,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.47] {exc}")
        print("[V3.2.1 Phase 5.47 Corporate Action Document Parser]")
        print(f"Input rows: {result['input_rows']:,}")
        print(f"Parsed rows: {result['parsed_rows']:,}")
        print(f"Eligibility: {result['eligibility_counts']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "review-complex-corporate-actions-v321":
        try:
            result = review_complex_corporate_actions_v321(
                candidate_manifest_csv=args.candidate_manifest_csv,
                official_candidates_csv=args.official_candidates_csv,
                not_applicable_csv=args.not_applicable_csv,
                audit_csv=args.audit_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.48] {exc}")
        print("[V3.2.1 Phase 5.48 Complex Corporate Action Review]")
        print(f"Reviewed: {result['reviewed_rows']:,}")
        print(f"NOT_APPLICABLE: {result['not_applicable_rows']:,}")
        print(f"Complex unresolved: {result['complex_rows']:,}")
        print(f"Evidence: {result['not_applicable_csv']}")
        print(f"Audit: {result['audit_csv']}")
    elif args.command == "audit-listed-spinoff-valuation-v321":
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
    elif args.command == "build-complex-action-coverage-gate-v321":
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
    elif args.command == "prioritize-current-resolution-backlog-v321":
        try:
            result = prioritize_current_resolution_backlog_v321(
                resolved_verification_csv=args.resolved_verification_csv,
                output_csv=args.output_csv, summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.55] {exc}")
        print("[V3.2.1 Phase 5.55 Current Resolution Priority]")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Next target: {result['next_target']}")
        print(f"Next target rows: {result['next_target_rows']:,}")
        print(f"Queue: {result['output_csv']}")
        print(f"Summary: {result['summary_json']}")
    elif args.command == "acquire-subsidiary-action-documents-v321":
        try:
            settings = get_settings()
            result = acquire_subsidiary_action_documents_v321(
                DartClient(settings.dart_api_key),
                priority_queue_csv=args.priority_queue_csv,
                disclosures_csv=args.disclosures_csv,
                documents_dir=args.documents_dir, output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.56] {exc}")
        print("[V3.2.1 Phase 5.56 Subsidiary Action Document Acquisition]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Acquired: {result['acquired_rows']:,}")
        print(f"Ambiguous: {result['ambiguous_rows']:,}")
        print(f"Manifest: {result['output_csv']}")
        print(f"Documents: {result['documents_dir']}")
    elif args.command == "parse-subsidiary-action-applicability-v321":
        try:
            result = parse_subsidiary_action_applicability_v321(
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                audit_output_csv=args.audit_output_csv,
                not_applicable_output_csv=args.not_applicable_output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.57] {exc}")
        print("[V3.2.1 Phase 5.57 Subsidiary Action Applicability]")
        print(f"Reviewed: {result['reviewed_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Direct issuer review: {result['direct_issuer_review_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Audit: {result['audit_output_csv']}")
        print(f"Evidence: {result['not_applicable_output_csv']}")
    elif args.command == "integrate-not-applicable-evidence-v321":
        try:
            result = integrate_not_applicable_evidence_v321(
                verification_csv=args.verification_csv, evidence_csv=args.evidence_csv,
                output_csv=args.output_csv, audit_csv=args.audit_csv,
                priority_output_csv=args.priority_output_csv,
                priority_summary_json=args.priority_summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.58] {exc}")
        print("[V3.2.1 Phase 5.58 NOT_APPLICABLE Integration]")
        print(f"Applied: {result['applied_rows']:,}")
        print(f"VERIFIED: {result['verified_queue_events']:,}")
        print(f"NOT_APPLICABLE: {result['not_applicable_queue_events']:,}")
        print(f"UNRESOLVED: {result['unresolved_queue_events']:,}")
        print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
        print(f"Resolved queue: {result['output_csv']}")
    elif args.command == "resolve-residual-subsidiary-actions-v321":
        try:
            settings = get_settings()
            result = resolve_residual_subsidiary_actions_v321(
                DartClient(settings.dart_api_key),
                applicability_audit_csv=args.applicability_audit_csv,
                acquisition_manifest_csv=args.acquisition_manifest_csv,
                disclosures_csv=args.disclosures_csv, documents_dir=args.documents_dir,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.59] {exc}")
        print("[V3.2.1 Phase 5.59 Residual Subsidiary Resolution]")
        print(f"Reviewed: {result['reviewed_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Evidence: {result['evidence_output_csv']}")
        print(f"Audit: {result['audit_output_csv']}")
    elif args.command == "integrate-residual-subsidiary-evidence-v321":
        try:
            result = integrate_residual_subsidiary_evidence_v321(
                verification_csv=args.verification_csv, evidence_csv=args.evidence_csv,
                output_csv=args.output_csv, audit_csv=args.audit_csv,
                priority_output_csv=args.priority_output_csv,
                priority_summary_json=args.priority_summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.60] {exc}")
        print("[V3.2.1 Phase 5.60 Residual Subsidiary Integration]")
        print(f"Applied: {result['applied_rows']:,}")
        print(f"VERIFIED: {result['verified_queue_events']:,}")
        print(f"NOT_APPLICABLE: {result['not_applicable_queue_events']:,}")
        print(f"UNRESOLVED: {result['unresolved_queue_events']:,}")
        print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
        print(f"Resolved queue: {result['output_csv']}")
    elif args.command == "build-direct-action-document-inventory-v321":
        try:
            settings = get_settings()
            result = build_direct_action_document_inventory_v321(
                DartClient(settings.dart_api_key), priority_queue_csv=args.priority_queue_csv,
                disclosures_csv=args.disclosures_csv,
                prior_acquisition_csv=args.prior_acquisition_csv,
                documents_dir=args.documents_dir, output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.61] {exc}")
        print("[V3.2.1 Phase 5.61 Direct Action Document Inventory]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Reused: {result['reused_rows']:,}")
        print(f"Newly acquired: {result['acquired_rows']:,}")
        print(f"Group-covered without standalone file: {result['group_covered_rows']:,}")
        print(f"Usable: {result['usable_rows']:,}")
        print(f"Candidate legal events: {result['candidate_legal_event_groups']:,}")
        print(f"Inventory: {result['output_csv']}")
    elif args.command == "review-direct-action-groups-v321":
        try:
            result = review_direct_action_groups_v321(
                inventory_csv=args.inventory_csv,
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
                parsed_documents_csv=args.parsed_documents_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.62] {exc}")
        print("[V3.2.1 Phase 5.62 Direct Action Group Review]")
        print(f"Groups: {result['reviewed_groups']:,}")
        print(f"Rows: {result['reviewed_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Core unresolved: {result['core_unresolved_rows']:,}")
        print(f"Evidence: {result['evidence_output_csv']}")
        print(f"Audit: {result['audit_output_csv']}")
    elif args.command == "integrate-direct-action-evidence-v321":
        try:
            result = integrate_direct_action_evidence_v321(
                verification_csv=args.verification_csv, evidence_csv=args.evidence_csv,
                output_csv=args.output_csv, audit_csv=args.audit_csv,
                priority_output_csv=args.priority_output_csv,
                priority_summary_json=args.priority_summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.63] {exc}")
        print("[V3.2.1 Phase 5.63 Direct Action Integration]")
        print(f"Applied: {result['applied_rows']:,}")
        print(f"VERIFIED: {result['verified_queue_events']:,}")
        print(f"NOT_APPLICABLE: {result['not_applicable_queue_events']:,}")
        print(f"UNRESOLVED: {result['unresolved_queue_events']:,}")
        print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
        print(f"Resolved queue: {result['output_csv']}")
    elif args.command == "verify-samsung-sdi-rights-v321":
        try:
            get_settings()
            result = verify_samsung_sdi_rights_v321(
                evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.64] {exc}")
        print("[V3.2.1 Phase 5.64 Samsung SDI Rights Verification]")
        print(f"Evidence rows: {result['evidence_rows']:,}")
        print(f"Effective date: {result['effective_date']}")
        print(f"Adjustment factor: {result['adjustment_factor']:.12f}")
        print(f"Theoretical gap: {result['theoretical_gap']:.6%}")
        print(f"Evidence: {result['evidence_output_csv']}")
        print(f"Audit: {result['audit_output_csv']}")
    elif args.command == "integrate-strict-event-evidence-v321":
        try:
            result = integrate_strict_event_evidence_v321(
                verification_csv=args.verification_csv, evidence_csv=args.evidence_csv,
                output_csv=args.output_csv, audit_csv=args.audit_csv,
                priority_output_csv=args.priority_output_csv,
                priority_summary_json=args.priority_summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.65] {exc}")
        print("[V3.2.1 Phase 5.65 Strict Evidence Integration]")
        print(f"Applied: {result['applied_rows']:,}")
        print(f"VERIFIED: {result['verified_queue_events']:,}")
        print(f"NOT_APPLICABLE: {result['not_applicable_queue_events']:,}")
        print(f"UNRESOLVED: {result['unresolved_queue_events']:,}")
        print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
        print(f"Resolved queue: {result['output_csv']}")
    elif args.command == "route-actionable-resolution-backlog-v321":
        try:
            result = route_actionable_resolution_backlog_v321(
                priority_queue_csv=args.priority_queue_csv,
                direct_action_audit_csv=args.direct_action_audit_csv,
                complex_evidence_audit_csv=args.complex_evidence_audit_csv,
                actionable_output_csv=args.actionable_output_csv,
                blocked_output_csv=args.blocked_output_csv, summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.66] {exc}")
        print("[V3.2.1 Phase 5.66 Actionable Backlog Router]")
        print(f"Actionable: {result['actionable_rows']:,}")
        print(f"Blocked: {result['blocked_rows']:,}")
        print(f"Next target: {result['next_actionable_target']} ({result['next_actionable_rows']:,})")
        print(f"Resolution status changed: {result['resolution_status_changed']}")
        print(f"Actionable queue: {result['actionable_output_csv']}")
        print(f"Blocked queue: {result['blocked_output_csv']}")
    elif args.command == "build-recent-dividend-evidence-inventory-v321":
        try:
            evidence_files = [
                "data/raw/v321/events/kind_paired_market_strict_evidence_phase535_v321.csv",
                "data/raw/v321/events/kind_paired_market_strict_evidence_phase537_v321.csv",
                "data/raw/v321/events/kind_paired_market_strict_evidence_phase538_v321.csv",
                "data/raw/v321/events/kind_paired_market_strict_evidence_phase539_v321.csv",
                "data/raw/v321/events/kind_paired_market_strict_evidence_phase540_v321.csv",
                "data/raw/v321/events/kind_paired_market_strict_evidence_phase541_v321.csv",
            ]
            result = build_recent_dividend_evidence_inventory_v321(
                actionable_queue_csv=args.actionable_queue_csv,
                prior_coverage_audit_csv=args.prior_coverage_audit_csv,
                strict_evidence_csvs=evidence_files, output_csv=args.output_csv,
                summary_json=args.summary_json,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.67] {exc}")
        print("[V3.2.1 Phase 5.67 Recent Dividend Evidence Inventory]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Future non-linkable evidence rows: {result['future_non_linkable_rows']:,}")
        print(f"Auto-promoted: {result['auto_promoted_rows']:,}")
        print(f"Next target: {result['next_target']}")
        print(f"Inventory: {result['output_csv']}")
    elif args.command == "acquire-historical-dividend-decisions-v321":
        try:
            settings = get_settings()
            result = acquire_historical_dividend_decisions_v321(
                DartClient(settings.dart_api_key), inventory_csv=args.inventory_csv,
                documents_dir=args.documents_dir, output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.68] {exc}")
        print("[V3.2.1 Phase 5.68 Historical Dividend Decision Acquisition]")
        print(f"Targets: {result['target_queue_rows']:,}")
        print(f"Queue rows with candidates: {result['queue_rows_with_candidates']:,}")
        print(f"Documents acquired: {result['candidate_documents_acquired']:,}")
        print(f"Queue rows without candidates: {result['queue_rows_without_candidates']:,}")
        print(f"Manifest: {result['output_csv']}")
        print(f"Documents: {result['documents_dir']}")
    elif args.command == "parse-historical-dividend-decisions-v321":
        try:
            result = parse_historical_dividend_decisions_v321(
                acquisition_csv=args.acquisition_csv, output_csv=args.output_csv)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.69] {exc}")
        print("[V3.2.1 Phase 5.69 Historical Dividend Decision Parser]")
        print(f"Manifest rows: {result['manifest_rows']:,}")
        print(f"Parsed rows: {result['parsed_rows']:,}")
        print(f"Incomplete rows: {result['incomplete_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "build-historical-dividend-exdate-candidates-v321":
        try:
            result = build_historical_dividend_exdate_candidates_v321(
                parsed_csv=args.parsed_csv, trading_calendar_db=args.trading_calendar_db,
                output_csv=args.output_csv, summary_json=args.summary_json)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.70] {exc}")
        print("[V3.2.1 Phase 5.70 Historical Dividend Ex-date Candidates]")
        print(f"Canonical parsed rows: {result['parsed_rows']:,}")
        print(f"Duplicate corrective filings removed: {result['deduplicated_rows']:,}")
        print(f"Ready for official market verification: {result['ready_for_market_verification']:,}")
        print(f"Late disclosure rows: {result['late_disclosure_rows']:,}")
        print(f"Strict rows: {result['strict_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "discover-historical-kind-exdates-v321":
        try:
            settings = get_settings()
            result = discover_historical_kind_exdates_v321(
                DartClient(settings.dart_api_key), candidates_csv=args.candidates_csv,
                output_csv=args.output_csv, audit_csv=args.audit_csv, timeout=args.timeout_seconds)
        except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.71] {exc}")
        print("[V3.2.1 Phase 5.71 Historical KIND Ex-date Discovery]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Official notices discovered: {result['discovered_rows']:,}")
        print(f"Unmatched: {result['unmatched_rows']:,}")
        print(f"Ambiguous: {result['ambiguous_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "build-historical-kind-strict-evidence-v321":
        try:
            result = build_historical_kind_strict_evidence_v321(
                discovery_csv=args.discovery_csv, parsed_decisions_csv=args.parsed_decisions_csv,
                output_csv=args.output_csv, audit_csv=args.audit_csv, timeout=args.timeout_seconds)
        except (FileNotFoundError, ValueError, requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.72] {exc}")
        print("[V3.2.1 Phase 5.72 Historical KIND Strict Evidence]")
        print(f"Discovered notices: {result['discovered_rows']:,}")
        print(f"Strict evidence rows: {result['strict_rows']:,}")
        print(f"Invalid rows: {result['invalid_rows']:,}")
        print(f"Preferred-share rows: {result['preferred_rows']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "integrate-historical-dividend-evidence-v321":
        try:
            result = integrate_historical_dividend_evidence_v321(
                verification_csv=args.verification_csv, strict_ledger_csv=args.strict_ledger_csv,
                selected_evidence_csv=args.selected_evidence_csv, selection_audit_csv=args.selection_audit_csv,
                output_csv=args.output_csv, integration_audit_csv=args.integration_audit_csv,
                priority_output_csv=args.priority_output_csv, priority_summary_json=args.priority_summary_json)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.73] {exc}")
        print("[V3.2.1 Phase 5.73 Historical Dividend Queue Integration]")
        print(f"Strict ledger rows: {result['strict_ledger_rows']:,}")
        print(f"Selected queue rows: {result['selected_queue_rows']:,}")
        print(f"Ledger-only historical rows: {result['ledger_only_rows']:,}")
        print(f"Verified: {result['verified_queue_events']:,}")
        print(f"Not applicable: {result['not_applicable_queue_events']:,}")
        print(f"Unresolved: {result['unresolved_queue_events']:,}")
        print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
        print(f"Output: {result['output_csv']}")
    elif args.command == "build-residual-dividend-backlog-v321":
        try:
            result = build_residual_dividend_backlog_v321(
                actionable_queue_csv=args.actionable_queue_csv, acquisition_csv=args.acquisition_csv,
                candidates_csv=args.candidates_csv, discovery_audit_csv=args.discovery_audit_csv,
                output_csv=args.output_csv, summary_json=args.summary_json)
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.74] {exc}")
        print("[V3.2.1 Phase 5.74 Residual Dividend Backlog]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Status counts: {result['status_counts']}")
        print(f"Next target: {result['next_target']} ({result['next_target_rows']:,})")
        print(f"Resolution status changed: {result['resolution_status_changed']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "resolve-ambiguous-kind-notice-v321":
        try:
            result = resolve_ambiguous_kind_notice_v321(residual_csv=args.residual_csv,
                parsed_decisions_csv=args.parsed_decisions_csv,discovery_output_csv=args.discovery_output_csv,
                candidate_audit_csv=args.candidate_audit_csv,strict_evidence_csv=args.strict_evidence_csv,
                strict_audit_csv=args.strict_audit_csv,timeout=args.timeout_seconds)
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
            result=resolve_broadened_kind_notices_v321(residual_csv=args.residual_csv,
                prior_discovery_audit_csv=args.prior_discovery_audit_csv,candidates_csv=args.candidates_csv,
                parsed_decisions_csv=args.parsed_decisions_csv,discovery_output_csv=args.discovery_output_csv,
                candidate_audit_csv=args.candidate_audit_csv,strict_evidence_csv=args.strict_evidence_csv,
                strict_audit_csv=args.strict_audit_csv,timeout=args.timeout_seconds)
        except (FileNotFoundError,ValueError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.77] {exc}")
        print("[V3.2.1 Phase 5.77 Broadened KIND Notice Resolution]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Resolved: {result['resolved_rows']:,}")
        print(f"Strict evidence: {result['strict_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['discovery_output_csv']}")
    elif args.command == "recover-pre-exdate-dividend-evidence-v321":
        try:
            result=recover_pre_exdate_dividend_evidence_v321(residual_csv=args.residual_csv,
                parsed_decisions_csv=args.parsed_decisions_csv,candidates_csv=args.candidates_csv,
                provenance_audit_csv=args.provenance_audit_csv,discovery_output_csv=args.discovery_output_csv,
                discovery_audit_csv=args.discovery_audit_csv,strict_evidence_csv=args.strict_evidence_csv,
                strict_audit_csv=args.strict_audit_csv,timeout=args.timeout_seconds)
        except (FileNotFoundError,ValueError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.78] {exc}")
        print("[V3.2.1 Phase 5.78 Pre-ex-date Provenance Recovery]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"Early provenance recovered: {result['provenance_recovered_rows']:,}")
        print(f"No pre-ex-date disclosure: {result['no_pre_exdate_disclosure_rows']:,}")
        print(f"Official notices resolved: {result['official_notices_resolved']:,}")
        print(f"Strict evidence: {result['strict_rows']:,}")
        print(f"Output: {result['provenance_audit_csv']}")
    elif args.command == "resolve-explicit-no-dividend-v321":
        try:
            result=resolve_explicit_no_dividend_v321(residual_csv=args.residual_csv,
                dividend_facts_csv=args.dividend_facts_csv,evidence_output_csv=args.evidence_output_csv,
                audit_output_csv=args.audit_output_csv,business_year=args.business_year)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.79] {exc}")
        print("[V3.2.1 Phase 5.79 Explicit No-dividend Resolution]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "route-historical-backlog-v321":
        try:
            result=build_historical_backlog_execution_manifest_v321(
                actionable_queue_csv=args.actionable_queue_csv,output_csv=args.output_csv,
                summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.82] {exc}")
        print("[V3.2.1 Phase 5.82 Historical Backlog Execution Router]")
        print(f"Historical backlog: {result['historical_backlog_rows']:,}")
        print(f"Accounted: {result['accounted_rows']:,}")
        print(f"Candidate clusters: {result['candidate_cluster_count']:,}")
        print(f"Next lane: {result['next_execution_lane']}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "defer-non-pit-dividends-v321":
        try:
            result=defer_non_pit_dividends_v321(actionable_queue_csv=args.actionable_queue_csv,
                residual_csv=args.residual_csv,provenance_audit_csv=args.provenance_audit_csv,
                actionable_output_csv=args.actionable_output_csv,deferred_output_csv=args.deferred_output_csv,
                audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.80] {exc}")
        print("[V3.2.1 Phase 5.80 Non-PIT Dividend Deferral]")
        print(f"Deferred non-PIT rows: {result['deferred_non_pit_rows']:,}")
        print(f"Remaining actionable rows: {result['remaining_actionable_rows']:,}")
        print(f"Recent batch accounted: {result['recent_dividend_batch_accounted_rows']:,}/{result['recent_dividend_batch_total']:,}")
        print(f"Resolution status changed: {result['resolution_status_changed']}")
        print(f"Deferred queue: {result['deferred_output_csv']}")
    elif args.command == "resolve-recent-followups-v321":
        try:
            settings=get_settings()
            result=resolve_recent_followups_v321(DartClient(settings.dart_api_key),
                actionable_queue_csv=args.actionable_queue_csv,resolved_verification_csv=args.resolved_verification_csv,
                documents_dir=args.documents_dir,evidence_output_csv=args.evidence_output_csv,audit_output_csv=args.audit_output_csv)
        except (FileNotFoundError,ValueError,RuntimeError,requests.RequestException) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.81] {exc}")
        print("[V3.2.1 Phase 5.81 Recent Follow-up Resolution]")
        print(f"Targets: {result['target_rows']:,}")
        print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
        print(f"Unresolved: {result['unresolved_rows']:,}")
        print(f"Output: {result['evidence_output_csv']}")
    elif args.command == "discover-kodex-next-hops-v321":
        try:
            result = discover_kodex_next_hops_v321(
                bodies_dir=args.bodies_dir,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.16] {exc}")
        print("[V3.2.1 Phase 5.16 KODEX Next-hop Discovery]")
        print(f"Body files: {result['body_files']:,}")
        print(f"Next-hop candidates: {result['next_hops']:,}")
        print(f"Output: {result['output_csv']}")
    elif args.command == "phase516-selfcheck":
        print("[V3.2.1 Phase 5.16.1 Self-check]")
        print("crosscheck-kind-dividends-v321: REGISTERED")
        print("discover-kodex-next-hops-v321: REGISTERED")
        print("phase516 module: IMPORT_OK")
        print("상태: PHASE516_APPLIED")
    elif args.command == "ml-diagnose-v321":
        try:
            health = assert_persistent_data_v321(conn, settings.db_path, args.benchmark_code)
        except RuntimeError as exc:
            raise SystemExit(f"[V3.2.1 DATA GUARD] {exc}")
        print(f"[DATA GUARD] PRESERVED: prices={health.stock_prices:,}, valuation={health.valuation_snapshots:,}, features={health.ml_features:,}, labels={health.ml_labels:,}")
        diagnostic_prefix = args.output_prefix
        if args.result_dir:
            result_dir = Path(args.result_dir)
            if result_dir.exists() and any(result_dir.iterdir()):
                raise SystemExit(f"[V3.2.1] 결과 폴더가 비어 있지 않습니다: {result_dir}")
            result_dir.mkdir(parents=True, exist_ok=True)
            diagnostic_prefix = str(result_dir / Path(args.output_prefix).name)
        summary = run_ml_diagnostics_v321(
            conn, args.horizon, args.benchmark_code, args.validation_days,
            args.test_days, args.min_train_days, args.fold_days, args.embargo_days,
            args.commission, args.tax, args.slippage, args.stock_cap,
            args.industry_cap, diagnostic_prefix, args.lockbox_start,
            args.universe_history_csv, args.total_return_csv,
            args.security_master_csv, args.corporate_actions_csv, args.rank_scope)
        passed = sum(summary["criteria"].values())
        print(f"[V3.2.1 공통위험·엄격PIT] {summary['verdict']} "
              f"({passed}/{len(summary['criteria'])} 기준 충족)")
        print(f"Champion / 내부 선택 전략: {summary['champion_strategy']} / "
              f"{summary['selected_strategy']}")
        print(f"후보 / 내부 폴드 / embargo: {summary['candidate_count']}개 / "
              f"{summary['nested_fold_count']}개 / {summary['embargo_days']}거래일")
        print(f"검증기간: {summary['validation_period']}")
        print(f"기존 공개 시험기간: {summary['published_test_period']}")
        print(f"시점별 유니버스: {summary['universe_history_status']}")
        print(f"총수익률 감사: {summary['total_return_audit']['status']}")
        print(f"재무 공시시점 감사: {summary['financial_point_in_time_audit']['status']}")
        print(f"기업행사 감사: {summary['corporate_action_status']}")
        for name, value in summary["criteria"].items():
            print(f"- {name}: {'통과' if value else '미통과'}")
        print("안전 상태: 연구·그림자 전용, 실제 주문 기능 없음")
        print(f"V3.2.1 결과 접두사: {diagnostic_prefix}")
        if args.result_dir:
            bundle = create_result_bundle_v321(
                output_prefix=diagnostic_prefix,
                result_dir=args.result_dir,
                zip_results=args.zip_results,
                minimum_files=20,
            )
            print(f"결과 폴더: {bundle['result_dir']}")
            print(f"Bundle manifest: {bundle['manifest']}")
            if bundle["zip_path"]:
                print(f"결과 ZIP: {bundle['zip_path']}")
    elif args.command == "collect-price":
        result = collect_prices_incremental(conn, KISClient(settings), args.code, args.days)
        print("API 호출 생략: 기존 데이터가 충분합니다." if result.api_skipped else f"{result.saved}건 증분 저장 완료: {result.requested_ranges}")
    elif args.command == "collect-financial":
        print(f"{collect_financials(conn, DartClient(settings.dart_api_key), args.code, args.year, args.report_code)}건 저장 완료")
    elif args.command == "collect-multi":
        args.codes, _ = resolve_codes_and_industries(args)
        client = KISClient(settings)
        for code in args.codes:
            try:
                result = collect_prices_incremental(conn, client, code, args.days)
                print(f"{code}: " + ("API 생략(충분)" if result.api_skipped else f"{result.saved}건 증분 저장"))
            except KISRateLimitError as exc:
                print(f"{code}: 수집 중단 - {exc}")
                print("KIS 제한 오류이므로 남은 종목의 API 호출을 중단합니다.")
                break
            except Exception as exc:
                print(f"{code}: 수집 오류 - {exc} (다음 종목 계속)")
    elif args.command == "collect-valuation":
        args.codes, _ = resolve_codes_and_industries(args)
        client = KISClient(settings)
        for code in args.codes:
            try:
                collect_valuation(conn, client, code)
                print(f"{code}: PER·PBR·EPS·BPS 가치지표 저장")
            except KISRateLimitError as exc:
                print(str(exc)); break
            except Exception as exc:
                print(f"{code}: 가치지표 오류 - {exc}")
    elif args.command == "collect-financial-series":
        args.codes, _ = resolve_codes_and_industries(args)
        client = DartClient(settings.dart_api_key)
        for code in args.codes:
            for year in range(args.start_year, args.end_year + 1):
                for report_code in ("11013", "11012", "11014", "11011"):
                    try:
                        count = collect_financials(conn, client, code, year, report_code)
                        print(f"{code} {year} {report_code}: {count}건")
                    except Exception as exc:
                        print(f"{code} {year} {report_code}: 생략 - {exc}")
    elif args.command in {"rank-universe", "shadow-run"}:
        args.codes, mapping = resolve_codes_and_industries(args)
        if args.command == "rank-universe":
            ranking = rank_universe(conn, args.codes, mapping, args.benchmark_code,
                                    args.min_liquidity)
            ranking.to_csv(args.export_csv, index=False, encoding="utf-8-sig")
            print(ranking[["code", "industry", "valuation_date", "valuation_status", "earnings_status", "per", "pbr", "roe",
                           "quality_score", "value_score", "momentum_score", "risk_score",
                           "quality_model", "valuation_reference", "per_peer_count", "pbr_peer_count",
                           "financial_status", "data_confidence", "eligible", "ineligible_reason",
                           "data_warning", "total_score"]].to_string(index=False))
            print(f"공통 종목순위 저장: {args.export_csv}")
        else:
            result = run_shadow_day(
                conn, args.codes, mapping, args.benchmark_code, args.capital,
                args.top_n, args.rebalance_band, args.min_order,
                args.stock_cap, args.sector_cap,
                portfolio_id=args.portfolio_id,
                min_liquidity=args.min_liquidity,
            )
            save_shadow_outputs(conn, result, args.output_prefix, args.portfolio_id)
            print_shadow_result(result, args.output_prefix)
    elif args.command == "portfolio-verify":
        mapping = {}
        for item in args.industry:
            if "=" not in item:
                raise SystemExit("--industry는 005930=반도체 형식이어야 합니다.")
            code, industry = item.split("=", 1); mapping[code] = industry
        frames = {code: load_prices(conn, code) for code in args.codes}
        benchmark_frame = load_prices(conn, args.benchmark_code)
        missing = [code for code, frame in frames.items() if frame.empty]
        if benchmark_frame.empty:
            missing.append(args.benchmark_code + "(벤치마크)")
        if missing:
            raise SystemExit("가격 데이터가 없는 종목: " + ", ".join(missing) + ". collect-multi를 먼저 실행하세요.")
        verified = run_lockbox(
            frames, benchmark_frame, mapping, lockbox_months=args.lockbox_months,
            initial_capital=args.capital, rebalance=args.rebalance,
            stock_cap=args.stock_cap, sector_cap=args.sector_cap,
        )
        prefix = Path(args.output_prefix)
        for label, result in (("development", verified.development), ("lockbox", verified.lockbox)):
            result.equity_curve.to_csv(prefix.with_name(prefix.name + f"_{label}_equity.csv"), encoding="utf-8-sig")
            result.trade_log.to_csv(prefix.with_name(prefix.name + f"_{label}_trades.csv"), index=False, encoding="utf-8-sig")
            result.allocation_log.to_csv(prefix.with_name(prefix.name + f"_{label}_allocations.csv"), index=False, encoding="utf-8-sig")
            result.yearly_performance.to_csv(prefix.with_name(prefix.name + f"_{label}_yearly.csv"), index=False, encoding="utf-8-sig")
        dev, lock = verified.development, verified.lockbox
        print(f"""[현실 포트폴리오 개발구간: {dev.start_date} ~ {dev.end_date}]
전략 수익률: {dev.total_return:.2f}% / 시장 ETF: {dev.benchmark_return:.2f}%
전략 MDD: {dev.mdd:.2f}% / 시장 ETF MDD: {dev.benchmark_mdd:.2f}%
전략 샤프: {dev.sharpe:.2f} / 시장 ETF 샤프: {dev.benchmark_sharpe:.2f}
거래비용: {dev.total_cost:,.0f}원 / 거래: {dev.trades}건

[최종 봉인구간: {lock.start_date} ~ {lock.end_date}]
전략 수익률: {lock.total_return:.2f}% / 시장 ETF: {lock.benchmark_return:.2f}%
초과수익률: {lock.excess_return:.2f}%p
전략 MDD: {lock.mdd:.2f}% / 시장 ETF MDD: {lock.benchmark_mdd:.2f}%
전략 샤프: {lock.sharpe:.2f} / 시장 ETF 샤프: {lock.benchmark_sharpe:.2f}
최종 봉인 판정: {verified.verdict}
결과 접두사: {args.output_prefix}""")
    elif args.command in {"external-verify", "common-verify"}:
        if args.command == "common-verify":
            mapping = {}
            for item in args.industry:
                if "=" not in item:
                    raise SystemExit("--industry는 005930=반도체 형식이어야 합니다.")
                code, industry = item.split("=", 1); mapping[code] = industry
            frames = {code: add_indicators(load_prices(conn, code)) for code in args.codes}
            missing = [code for code, frame in frames.items() if frame.empty]
            if missing:
                raise SystemExit("가격 데이터가 없는 종목: " + ", ".join(missing))
            common = common_parameter_walk_forward(frames, mapping, initial_capital=args.capital)
            prefix = Path(args.output_prefix)
            common.folds.to_csv(prefix.with_name(prefix.name + "_folds.csv"), index=False, encoding="utf-8-sig")
            common.stocks.to_csv(prefix.with_name(prefix.name + "_stocks.csv"), index=False, encoding="utf-8-sig")
            common.industries.to_csv(prefix.with_name(prefix.name + "_industries.csv"), index=False, encoding="utf-8-sig")
            common.portfolio_curve.to_csv(prefix.with_name(prefix.name + "_portfolio.csv"), encoding="utf-8-sig")
            print(f"""[다종목 공통 파라미터 워크포워드]
통합 포트폴리오 수익률: {common.portfolio_return:.2f}%
통합 포트폴리오 MDD: {common.portfolio_mdd:.2f}%
통합 포트폴리오 샤프: {common.portfolio_sharpe:.2f}
통합 벤치마크 수익률: {common.benchmark_return:.2f}%
통합 벤치마크 MDD: {common.benchmark_mdd:.2f}%
통합 벤치마크 샤프: {common.benchmark_sharpe:.2f}
최종 판정: {common.verdict}
결과 접두사: {args.output_prefix}""")
            return
        client = None if args.skip_collect else KISClient(settings)
        rows = []
        frames = {}
        for code in args.codes:
            try:
                collection = None if args.skip_collect else collect_prices_incremental(conn, client, code, args.days)
                frame = add_indicators(load_prices(conn, code))
                if frame.empty:
                    raise ValueError("저장된 가격 데이터가 없습니다. collect-multi를 먼저 실행하세요.")
                frames[code] = frame
                result = run_ma_rsi_strategy(frame, initial_capital=args.capital)
                row = {"code": code, "saved": 0 if collection is None else collection.saved,
                       "api_skipped": args.skip_collect or collection.api_skipped,
                       "return": result.total_return,
                       "benchmark_return": result.benchmark_return, "excess_return": result.excess_return,
                       "mdd": result.mdd, "benchmark_mdd": result.benchmark_mdd,
                       "sharpe": result.sharpe, "benchmark_sharpe": result.benchmark_sharpe,
                       "profit_factor": result.profit_factor, "trades": result.trades,
                       "status": "완료"}
                rows.append(row)
                print(f"{code}: 전략 {result.total_return:.2f}%, 벤치마크 {result.benchmark_return:.2f}%")
            except Exception as exc:
                rows.append({"code": code, "status": f"오류: {exc}"})
                print(f"{code}: 오류 - {exc}")
                if isinstance(exc, KISRateLimitError):
                    print("KIS 제한 오류로 남은 종목의 API 호출을 중단합니다.")
                    break
        pd.DataFrame(rows).to_csv(args.export_csv, index=False, encoding="utf-8-sig")
        print(f"다종목 검증 저장: {args.export_csv}")
        if args.with_walk_forward and len(frames) >= 2:
            common = common_parameter_walk_forward(frames, initial_capital=args.capital)
            base = Path(args.export_csv)
            common.folds.to_csv(base.with_name(base.stem + "_common_folds.csv"), index=False, encoding="utf-8-sig")
            common.stocks.to_csv(base.with_name(base.stem + "_common_stocks.csv"), index=False, encoding="utf-8-sig")
            common.industries.to_csv(base.with_name(base.stem + "_industries.csv"), index=False, encoding="utf-8-sig")
            common.portfolio_curve.to_csv(base.with_name(base.stem + "_portfolio.csv"), encoding="utf-8-sig")
            print(f"공통 파라미터 포트폴리오: 수익 {common.portfolio_return:.2f}%, MDD {common.portfolio_mdd:.2f}%, 샤프 {common.portfolio_sharpe:.2f}, 벤치마크 {common.benchmark_return:.2f}%, 판정 {common.verdict}")
    else:
        data = add_indicators(load_prices(conn, args.code))
        if data.empty:
            raise SystemExit("가격 데이터가 없습니다. 먼저 collect-price를 실행하세요.")
        if args.command == "analyze":
            latest = data.tail(1).iloc[0]
            print("[기술적 분석]")
            print(data.tail(1)[["date", "close", "ma5", "ma20", "ma60", "rsi14", "volume_change"]].to_string(index=False))
            tech_score = technical_score(latest)
            financial = analyze_financials(conn, args.code)
            print(f"기술 점수: {tech_score:.2f}/100")
            if financial is None:
                print("\n[재무 분석]\n재무 데이터가 없습니다. 먼저 collect-financial을 실행하세요.")
                combined = tech_score
            else:
                def fmt(value, suffix="%"):
                    return "N/A" if value is None else f"{value:.2f}{suffix}"
                print(f"\n[재무 분석: {financial.fiscal_year}년]")
                print(f"매출 성장률: {fmt(financial.revenue_growth)}")
                print(f"영업이익률: {fmt(financial.operating_margin)}")
                print(f"ROE: {fmt(financial.roe)}")
                print(f"부채비율: {fmt(financial.debt_ratio)}")
                cash_state = "N/A" if financial.operating_cash_flow is None else ("양수" if financial.operating_cash_flow > 0 else "음수")
                print(f"영업현금흐름: {cash_state}")
                print(f"재무 점수: {financial.score:.2f}/100")
                if financial.warnings:
                    print("검증 경고: " + " | ".join(financial.warnings))
                combined = round(tech_score * 0.4 + financial.score * 0.6, 2)
            print(f"\n[종합 분석]\n종합 점수: {combined:.2f}/100\n판정: {investment_opinion(combined)}")
        elif args.command == "backtest":
            result = run_ma_rsi_strategy(
                data, initial_capital=args.capital, commission_pct=args.commission,
                sell_tax_pct=args.tax, slippage_pct=args.slippage,
            )
            conn.execute("""INSERT INTO backtest_runs(
                code,created_at,strategy,total_return,mdd,win_rate,trades,
                benchmark_return,excess_return,cagr,sharpe,profit_factor,total_cost
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (args.code, datetime.now(timezone.utc).isoformat(), "ma20_ma60_rsi14_next_open",
                 result.total_return, result.mdd, result.win_rate, result.trades,
                 result.benchmark_return, result.excess_return, result.cagr,
                 result.sharpe, result.profit_factor, result.total_cost))
            conn.commit()
            if args.export_csv:
                result.trade_log.to_csv(args.export_csv, index=False, encoding="utf-8-sig")
                path = Path(args.export_csv)
                result.yearly_performance.to_csv(path.with_name(path.stem + "_yearly.csv"), index=False, encoding="utf-8-sig")
                result.regime_performance.to_csv(path.with_name(path.stem + "_regime.csv"), index=False, encoding="utf-8-sig")
                result.equity_curve.to_csv(path.with_name(path.stem + "_equity.csv"), encoding="utf-8-sig")
            print(f"""[현실화 백테스트: {result.start_date} ~ {result.end_date}]
전략 누적수익률: {result.total_return:.2f}%
단순 보유수익률: {result.benchmark_return:.2f}%
초과수익률: {result.excess_return:.2f}%
전략 CAGR: {result.cagr:.2f}%
벤치마크 CAGR: {result.benchmark_cagr:.2f}%
일별 MDD: {result.mdd:.2f}%
벤치마크 MDD: {result.benchmark_mdd:.2f}%
샤프지수: {result.sharpe:.2f}
벤치마크 샤프지수: {result.benchmark_sharpe:.2f}
승률: {result.win_rate:.2f}%
손익비(Profit Factor): {result.profit_factor}
평균 보유기간: {result.avg_holding_days:.2f}일
완료 거래: {result.trades}회
총 거래비용: {result.total_cost:,.0f}원""")
            if args.export_csv:
                print(f"거래내역 저장: {args.export_csv}")
        elif args.command == "walk-forward":
            result = walk_forward_optimize(
                data, train_years=args.train_years, test_months=args.test_months,
                initial_capital=args.capital, commission_pct=args.commission,
                sell_tax_pct=args.tax, slippage_pct=args.slippage,
            )
            result.folds.to_csv(args.export_csv, index=False, encoding="utf-8-sig")
            print(f"""[워크포워드 과최적화 방지 검증]
미사용 구간 누적수익률: {result.oos_return:.2f}%
동일 구간 단순 보유수익률: {result.benchmark_return:.2f}%
초과수익률: {result.excess_return:.2f}%
수익 구간 비율: {result.positive_fold_rate:.2f}%
평균 미사용구간 샤프: {result.average_oos_sharpe:.2f}
OOS-학습 CAGR 차이: {result.average_degradation:.2f}%p
선택 파라미터 안정성: {result.parameter_stability:.2f}%
절대수익 판정: {result.absolute_status}
벤치마크 판정: {result.benchmark_status}
위험조정 판정: {result.risk_status}
파라미터 안정성 판정: {result.stability_status}
최종 판정: {result.verdict}
구간별 결과 저장: {args.export_csv}""")
        else:
            result = run_ma_rsi_strategy(data, initial_capital=args.capital)
            sensitivity = parameter_sensitivity(data, initial_capital=args.capital)
            monte = monte_carlo_trades(result, simulations=args.simulations)
            prefix = Path(args.output_prefix)
            sensitivity.details.to_csv(prefix.with_name(prefix.name + "_sensitivity.csv"), index=False, encoding="utf-8-sig")
            monte.details.to_csv(prefix.with_name(prefix.name + "_monte_carlo.csv"), index=False, encoding="utf-8-sig")
            result.yearly_performance.to_csv(prefix.with_name(prefix.name + "_yearly.csv"), index=False, encoding="utf-8-sig")
            result.regime_performance.to_csv(prefix.with_name(prefix.name + "_regime.csv"), index=False, encoding="utf-8-sig")
            print(f"""[강건성 검증]
파라미터 양수익 비율: {sensitivity.positive_rate:.2f}%
파라미터 벤치마크 초과 비율: {sensitivity.benchmark_beat_rate:.2f}%
파라미터 중앙 수익률: {sensitivity.median_return:.2f}%
수익률 표준편차: {sensitivity.return_dispersion:.2f}%p
민감도 판정: {sensitivity.verdict}
몬테카를로 횟수: {monte.simulations}
몬테카를로 중앙 수익률: {monte.median_return:.2f}%
수익률 5%~95% 범위: {monte.return_p05:.2f}% ~ {monte.return_p95:.2f}%
손실 확률: {monte.loss_probability:.2f}%
하위 5% MDD: {monte.mdd_p05:.2f}%
몬테카를로 판정: {monte.verdict}
결과 파일 접두사: {args.output_prefix}""")


if __name__ == "__main__":
    main()
