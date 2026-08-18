from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd

from src.analysis.indicators import add_indicators
from src.analysis.universe_ranker import rank_universe
from src.backtest.engine import run_ma_rsi_strategy
from src.backtest.multi_asset import common_parameter_walk_forward
from src.backtest.realistic_portfolio import run_lockbox
from src.collector.collectors import collect_prices_incremental
from src.kis.client import KISClient, KISRateLimitError
from src.shadow.engine import run_shadow_day


PORTFOLIO_COMMANDS = frozenset({
    "rank-universe",
    "shadow-run",
    "portfolio-verify",
    "external-verify",
    "common-verify",
})


def _load_prices(conn: sqlite3.Connection, code: str) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT date,open,high,low,close,volume FROM stock_prices "
        "WHERE code=? ORDER BY date",
        conn,
        params=(code,),
    )


def run_portfolio_command(
    conn: sqlite3.Connection,
    settings,
    args,
    *,
    resolve_codes,
    save_shadow_outputs,
    print_shadow_result,
) -> None:
    """Run portfolio research commands without any live-order capability."""
    if args.command not in PORTFOLIO_COMMANDS:
        raise ValueError(f"지원하지 않는 포트폴리오 명령입니다: {args.command}")

    if args.command in {"rank-universe", "shadow-run"}:
        args.codes, mapping = resolve_codes(args)
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
        frames = {code: _load_prices(conn, code) for code in args.codes}
        benchmark_frame = _load_prices(conn, args.benchmark_code)
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
            frames = {code: add_indicators(_load_prices(conn, code)) for code in args.codes}
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
                frame = add_indicators(_load_prices(conn, code))
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
