import argparse
import atexit
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import time
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from config.settings import get_settings
from database.database import connect
from src.collector.collectors import collect_prices_incremental, collect_valuation
from src.dart.client import DartClient
from src.kis.client import KISClient, KISRateLimitError
from src.ml.market_effective_date_v321 import PykrxMarketAdjustmentProvider
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
    from src.cli.ml_parsers import register_ml_parsers

    register_ml_parsers(sub)
    from src.cli.data_operation_parsers import register_data_operation_parsers

    register_data_operation_parsers(sub)
    from src.cli.event_reconciliation_parsers import register_event_reconciliation_parsers

    register_event_reconciliation_parsers(sub)
    from src.cli.official_event_parsers import register_official_event_parsers

    register_official_event_parsers(sub)
    from src.cli.cash_distribution_parsers import register_cash_distribution_parsers

    register_cash_distribution_parsers(sub)
    from src.cli.kodex_distribution_parsers import register_kodex_distribution_parsers

    register_kodex_distribution_parsers(sub)
    from src.cli.stock_dividend_evidence_parsers import register_stock_dividend_evidence_parsers

    register_stock_dividend_evidence_parsers(sub)
    from src.cli.kind_parsers import register_kind_parsers

    register_kind_parsers(sub)
    from src.cli.corporate_action_parsers import register_corporate_action_parsers

    register_corporate_action_parsers(sub)
    from src.cli.spinoff_parsers import register_spinoff_parsers

    register_spinoff_parsers(sub)
    from src.cli.subsidiary_action_parsers import register_subsidiary_action_parsers

    register_subsidiary_action_parsers(sub)
    from src.cli.direct_action_parsers import register_direct_action_parsers

    register_direct_action_parsers(sub)
    from src.cli.historical_dividend_parsers import register_historical_dividend_parsers

    register_historical_dividend_parsers(sub)
    from src.cli.historical_kind_parsers import register_historical_kind_parsers

    register_historical_kind_parsers(sub)
    from src.cli.dividend_resolution_parsers import register_dividend_resolution_parsers

    register_dividend_resolution_parsers(sub)
    from src.cli.dividend_backlog_parsers import register_dividend_backlog_parsers

    register_dividend_backlog_parsers(sub)
    from src.cli.historical_chain_parsers import register_historical_chain_parsers

    register_historical_chain_parsers(sub)
    from src.cli.primary_adjustment_parsers import register_primary_adjustment_parsers

    register_primary_adjustment_parsers(sub)
    from src.cli.adjustment_applicability_parsers import register_adjustment_applicability_parsers

    register_adjustment_applicability_parsers(sub)
    from src.cli.company_audit_parsers import register_company_audit_parsers

    register_company_audit_parsers(sub)
    from src.cli.release_parsers import register_release_parsers

    register_release_parsers(sub)
    from src.cli.kind_followup_parsers import register_kind_followup_parsers

    register_kind_followup_parsers(sub)
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
    if args.command in {
        "shadow-list",
        "daily-status",
        "ml-readiness",
        "shadow-report",
        "daily-shadow",
        "build-feature-store",
        "ml-train",
        "ml-walk-forward",
        "ml-predict",
    }:
        from src.cli.runtime_commands import run_runtime_command

        run_runtime_command(
            conn,
            settings,
            args,
            resolve_codes=resolve_codes_and_industries,
            print_shadow_report=print_shadow_report,
            execute_daily_shadow=execute_daily_shadow,
        )
    elif args.command in {
        "import-valuation-snapshots-v321",
        "build-data-foundation-v321",
        "krx-provider-check-v321",
        "acquire-historical-data-v321",
        "db-health-v321",
        "backup-db-v321",
    }:
        from src.cli.data_operation_commands import run_data_operation_command

        run_data_operation_command(conn, settings, args)
    elif args.command in {
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
    }:
        from src.cli.event_commands import run_event_command

        run_event_command(
            conn,
            settings,
            args,
            load_universe=load_universe_csv,
        )
    elif args.command in {
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
    }:
        from src.cli.dividend_commands import run_dividend_command

        run_dividend_command(conn, settings, args)
    elif args.command in {
        "crosscheck-kind-dividends-v321",
        "retry-kind-dividends-v321",
    }:
        from src.cli.kind_commands import run_kind_command

        run_kind_command(args)
    elif args.command == "validate-primary-adjustment-market-dates-v321":
        from src.cli.primary_adjustment_commands import run_primary_adjustment_command

        run_primary_adjustment_command(settings, args)
    elif args.command in {
        "verify-samsung-heavy-rights-v321",
        "audit-amorepacific-restructuring-v321",
        "audit-overseas-listing-delistings-v321",
    }:
        from src.cli.company_adjustment_commands import run_company_adjustment_command

        run_company_adjustment_command(settings, args)
    elif args.command in {
        "audit-lgchem-subsidiary-rights-v321",
        "audit-hdhyundai-exchangeable-bond-v321",
        "audit-ecoprobm-merger-transfer-v321",
    }:
        from src.cli.company_applicability_commands import run_company_applicability_command

        run_company_applicability_command(settings, args)
    elif args.command in {
        "audit-kakao-zero-ratio-merger-v321",
        "audit-celltrion-merger-followups-v321",
        "audit-kakao-overseas-dr-delisting-v321",
        "audit-samsung-heavy-preferred-delisting-warnings-v321",
    }:
        from src.cli.merger_followup_commands import run_merger_followup_command

        run_merger_followup_command(settings, args)
    elif args.command in {
        "audit-hd-ksoe-subsidiary-zero-ratio-merger-v321",
        "audit-ecoprobm-subsidiary-capital-increases-v321",
        "audit-lgchem-historical-subsidiary-capital-v321",
        "audit-amorepacific-us-subsidiary-capital-v321",
        "audit-skhynix-subsidiary-capital-v321",
        "audit-cj-schwans-subsidiary-mergers-v321",
        "audit-kakao-games-subsidiary-capital-v321",
    }:
        from src.cli.subsidiary_audit_commands import run_subsidiary_audit_command

        run_subsidiary_audit_command(settings, args)
    elif args.command in {
        "audit-naver-line-overseas-delisting-v321",
        "audit-historical-administrative-trading-halts-v321",
        "audit-related-party-rights-participation-v321",
    }:
        from src.cli.market_followup_audit_commands import run_market_followup_audit_command

        run_market_followup_audit_command(settings, args)
    elif args.command in {
        "audit-samsung-heavy-rights-price-followups-v321",
        "audit-asset-transfer-completion-reports-v321",
        "audit-physical-split-business-transfer-completions-v321",
    }:
        from src.cli.completion_followup_commands import run_completion_followup_command

        run_completion_followup_command(settings, args)
    elif args.command in {
        "audit-amorepacific-attachment-followups-v321",
        "audit-rights-offering-followups-v321",
        "audit-hdhyundai-subsidiary-rights-amendments-v321",
    }:
        from src.cli.amendment_followup_commands import run_amendment_followup_command

        run_amendment_followup_command(args)
    elif args.command in {
        "audit-kakao-split-amendments-v321",
        "audit-historical-amendment-duplicates-v321",
        "audit-ecoprobm-rights-support-disclosures-v321",
    }:
        from src.cli.amendment_crosscheck_commands import run_amendment_crosscheck_command

        run_amendment_crosscheck_command(args)
    elif args.command in {
        "verify-ecoprobm-bonus-issue-v321",
        "audit-hd-ksoe-third-party-capital-v321",
        "audit-shinhan-neoplux-share-exchange-v321",
    }:
        from src.cli.final_company_audit_commands import run_final_company_audit_command

        run_final_company_audit_command(settings, args)
    elif args.command in {
        "build-release-quality-gate-v321",
        "verify-release-artifact-integrity-v321",
        "verify-release-restore-drill-v321",
        "build-runtime-readiness-gate-v321",
        "build-release-candidate-seal-v321",
        "build-rc-promotion-readiness-v321",
        "build-release-approval-handoff-v321",
        "build-release-notes-v321",
        "build-repository-promotion-preflight-v321",
        "build-release-curation-manifest-v321",
        "build-manual-curation-resolution-v321",
        "build-curated-release-payload-v321",
        "verify-curated-payload-restore-v321",
        "build-final-promotion-gate-v321",
        "build-final-release-bundle-v321",
    }:
        from src.cli.release_commands import run_release_command

        run_release_command(args)
    elif args.command in {
        "audit-historical-merger-spinoff-applicability-v321",
        "reparse-celltrion-merger-v321",
        "audit-historical-capital-reductions-v321",
        "audit-incomplete-primary-adjustments-v321",
    }:
        from src.cli.adjustment_applicability_commands import run_adjustment_applicability_command

        run_adjustment_applicability_command(args)
    elif args.command == "audit-historical-rights-applicability-v321":
        from src.cli.primary_adjustment_commands import run_primary_adjustment_command

        run_primary_adjustment_command(settings, args)
    elif args.command == "consolidate-historical-legal-chains-v321":
        from src.cli.historical_chain_commands import run_historical_chain_command

        run_historical_chain_command(settings, args)
    elif args.command == "extract-primary-adjustment-document-terms-v321":
        from src.cli.primary_adjustment_commands import run_primary_adjustment_command

        run_primary_adjustment_command(settings, args)
    elif args.command in {
        "validate-historical-chain-documents-v321",
        "quarantine-periodic-dividend-aggregates-v321",
        "build-historical-legal-event-chain-v321",
    }:
        from src.cli.historical_chain_commands import run_historical_chain_command

        run_historical_chain_command(settings, args)
    elif args.command in {
        "parse-kind-dividends-v321",
        "reconcile-kind-dividends-v321",
        "acquire-kind-market-exdates-v321",
        "discover-kind-market-exdates-v321",
    }:
        from src.cli.kind_commands import run_kind_command

        run_kind_command(args)
    elif args.command in {
        "prioritize-resolution-gaps-v321",
        "build-recent-dividend-acquisition-manifest-v321",
        "recover-acquisition-company-names-v321",
    }:
        from src.cli.resolution_planning_commands import run_resolution_planning_command

        run_resolution_planning_command(args)
    elif args.command in {
        "discover-kind-market-notices-batch-v321",
        "acquire-paired-kind-dividend-decisions-v321",
        "build-paired-kind-market-observations-v321",
    }:
        from src.cli.kind_followup_commands import run_kind_followup_command

        run_kind_followup_command(args)
    elif args.command in {
        "acquire-direct-kind-dividend-decisions-v321",
        "extract-kind-aggregate-market-targets-v321",
    }:
        from src.cli.kind_followup_commands import run_kind_followup_command

        run_kind_followup_command(args)
    elif args.command in {
        "audit-market-notice-coverage-v321",
        "classify-recent-corporate-actions-v321",
    }:
        from src.cli.coverage_classification_commands import run_coverage_classification_command

        run_coverage_classification_command(args)
    elif args.command in {
        "build-corporate-action-candidate-manifest-v321",
        "select-market-adjustment-candidates-v321",
        "acquire-missing-corporate-action-documents-v321",
        "parse-corporate-action-documents-v321",
        "review-complex-corporate-actions-v321",
    }:
        from src.cli.corporate_action_document_commands import run_corporate_action_document_command

        run_corporate_action_document_command(settings, args)
    elif args.command in {
        "audit-listed-spinoff-valuation-v321",
        "build-spinoff-distribution-ledger-v321",
        "audit-spinoff-fractional-settlement-v321",
        "audit-spinoff-evidence-completeness-v321",
        "build-complex-action-coverage-gate-v321",
    }:
        from src.cli.spinoff_commands import run_spinoff_command

        run_spinoff_command(args)
    elif args.command in {
        "prioritize-current-resolution-backlog-v321",
        "acquire-subsidiary-action-documents-v321",
        "parse-subsidiary-action-applicability-v321",
        "integrate-not-applicable-evidence-v321",
        "resolve-residual-subsidiary-actions-v321",
        "integrate-residual-subsidiary-evidence-v321",
    }:
        from src.cli.subsidiary_action_commands import run_subsidiary_action_command

        run_subsidiary_action_command(settings, args)
    elif args.command in {
        "build-direct-action-document-inventory-v321",
        "review-direct-action-groups-v321",
        "integrate-direct-action-evidence-v321",
        "verify-samsung-sdi-rights-v321",
        "integrate-strict-event-evidence-v321",
        "route-actionable-resolution-backlog-v321",
    }:
        from src.cli.direct_action_commands import run_direct_action_command

        run_direct_action_command(settings, args)
    elif args.command in {
        "build-recent-dividend-evidence-inventory-v321",
        "acquire-historical-dividend-decisions-v321",
        "parse-historical-dividend-decisions-v321",
        "build-historical-dividend-exdate-candidates-v321",
    }:
        from src.cli.historical_dividend_commands import run_historical_dividend_command

        run_historical_dividend_command(settings, args)
    elif args.command in {
        "discover-historical-kind-exdates-v321",
        "build-historical-kind-strict-evidence-v321",
        "integrate-historical-dividend-evidence-v321",
        "build-residual-dividend-backlog-v321",
    }:
        from src.cli.historical_kind_commands import run_historical_kind_command

        run_historical_kind_command(settings, args)
    elif args.command in {
        "resolve-ambiguous-kind-notice-v321",
        "resolve-broadened-kind-notices-v321",
        "recover-pre-exdate-dividend-evidence-v321",
        "resolve-explicit-no-dividend-v321",
    }:
        from src.cli.dividend_resolution_commands import run_dividend_resolution_command

        run_dividend_resolution_command(args)
    elif args.command in {
        "defer-non-pit-dividends-v321",
        "resolve-recent-followups-v321",
        "route-historical-backlog-v321",
    }:
        from src.cli.dividend_backlog_commands import run_dividend_backlog_command

        run_dividend_backlog_command(settings, args)
    elif args.command in {"discover-kodex-next-hops-v321", "phase516-selfcheck"}:
        from src.cli.kodex_commands import run_kodex_command

        run_kodex_command(args)
    elif args.command == "ml-diagnose-v321":
        from src.cli.ml_diagnostic_commands import run_ml_diagnostic_command

        run_ml_diagnostic_command(conn, settings, args)
    elif args.command in {
        "collect-price",
        "collect-financial",
        "collect-multi",
        "collect-valuation",
        "collect-financial-series",
    }:
        from src.cli.collection_commands import run_collection_command

        run_collection_command(
            conn,
            settings,
            args,
            resolve_codes=resolve_codes_and_industries,
        )
    elif args.command in {
        "rank-universe",
        "shadow-run",
        "portfolio-verify",
        "external-verify",
        "common-verify",
    }:
        from src.cli.portfolio_commands import run_portfolio_command

        run_portfolio_command(
            conn,
            settings,
            args,
            resolve_codes=resolve_codes_and_industries,
            save_shadow_outputs=save_shadow_outputs,
            print_shadow_result=print_shadow_result,
        )
    else:
        from src.cli.core_commands import run_core_command

        run_core_command(conn, args)

if __name__ == "__main__":
    main()
