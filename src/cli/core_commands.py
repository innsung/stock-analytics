from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pandas as pd

from src.analysis.financial_score import (
    analyze_financials,
    investment_opinion,
    technical_score,
)
from src.analysis.indicators import add_indicators
from src.backtest.engine import run_ma_rsi_strategy
from src.backtest.robustness import monte_carlo_trades, parameter_sensitivity
from src.backtest.walk_forward import walk_forward_optimize


CORE_COMMANDS = frozenset({"analyze", "backtest", "walk-forward", "robustness"})


def _load_prices(conn: sqlite3.Connection, code: str) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT date,open,high,low,close,volume FROM stock_prices "
        "WHERE code=? ORDER BY date",
        conn,
        params=(code,),
    )


def run_core_command(conn: sqlite3.Connection, args) -> None:
    """Run one analysis/backtest command after argparse validation."""
    if args.command not in CORE_COMMANDS:
        raise ValueError(f"지원하지 않는 핵심 명령입니다: {args.command}")
    data = add_indicators(_load_prices(conn, args.code))
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

