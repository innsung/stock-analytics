from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import sqlite3

import pandas as pd

from src.analysis.universe_ranker import rank_universe
from src.backtest.realistic_portfolio import _capped_weights


STRATEGY_VERSION = "quality_value_momentum_v321_eligibility"


@dataclass
class ShadowResult:
    portfolio_id: str
    as_of: str
    equity: float
    cash: float
    daily_return: float
    cumulative_return: float
    benchmark_return: float
    cash_drag: float
    cash_opportunity_cost: float
    cash_defense: float
    already_processed: bool
    target_exposure: float
    actual_exposure: float
    allocation_gap: float
    proposals: pd.DataFrame = field(repr=False)
    skips: pd.DataFrame = field(repr=False)
    rankings: pd.DataFrame = field(repr=False)
    attribution: pd.DataFrame = field(repr=False)


def run_shadow_day(
    conn: sqlite3.Connection, codes: list[str], industries: dict[str, str],
    benchmark_code: str = "069500", initial_capital: float = 100_000_000,
    top_n: int = 10, rebalance_band: float = .02, min_order: float = 500_000,
    stock_cap: float = .15, sector_cap: float = .30,
    commission_pct: float = .015, sell_tax_pct: float = .18, slippage_pct: float = .05,
    portfolio_id: str = "default",
    min_liquidity: float = 1_000_000_000,
) -> ShadowResult:
    portfolio_id = portfolio_id.strip()
    if not portfolio_id or len(portfolio_id) > 50:
        raise ValueError("portfolio_id는 1~50자의 값이어야 합니다.")
    universe_payload = {"codes": sorted(codes),
                        "industries": {code: industries.get(code, "미분류") for code in sorted(codes)}}
    universe_json = json.dumps(universe_payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"))
    universe_hash = hashlib.sha256(universe_json.encode()).hexdigest()
    config_payload = {
        "strategy_version": STRATEGY_VERSION, "universe_hash": universe_hash,
        "benchmark_code": benchmark_code, "top_n": top_n,
        "rebalance_band": rebalance_band, "min_order": min_order,
        "stock_cap": stock_cap, "sector_cap": sector_cap,
        "commission_pct": commission_pct, "sell_tax_pct": sell_tax_pct,
        "slippage_pct": slippage_pct, "min_liquidity": min_liquidity,
        "initial_capital": initial_capital,
    }
    config_json = json.dumps(config_payload, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"))
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    stored_config = conn.execute(
        "SELECT config_hash FROM shadow_accounts WHERE portfolio_id=?", (portfolio_id,)
    ).fetchone()
    if stored_config and stored_config[0] is not None and stored_config[0] != config_hash:
        raise ValueError(
            f"포트폴리오 '{portfolio_id}'의 저장 설정과 현재 설정이 다릅니다. "
            "기존 성과를 보호하기 위해 실행을 중단했습니다. 새 --portfolio-id를 사용하세요."
        )
    if stored_config and stored_config[0] is None:
        conn.execute("""UPDATE shadow_accounts SET strategy_version=?,config_hash=?,
            config_json=?,universe_hash=?,updated_at=? WHERE portfolio_id=?""",
            (STRATEGY_VERSION, config_hash, config_json, universe_hash,
             datetime.now(timezone.utc).isoformat(), portfolio_id))
        conn.commit()
    ranking = rank_universe(conn, codes, industries, benchmark_code, min_liquidity)
    if ranking.empty:
        raise ValueError("순위를 계산할 가격·가치·재무 데이터가 부족합니다.")
    latest_dates = [conn.execute("SELECT MAX(date) FROM stock_prices WHERE code=?", (code,)).fetchone()[0]
                    for code in [*codes, benchmark_code]]
    if any(day is None for day in latest_dates):
        raise ValueError("가격 데이터가 없는 종목이 있습니다.")
    as_of = min(latest_dates)
    existing = conn.execute("""SELECT equity,cash,daily_return,cumulative_return,
        benchmark_return,cash_drag,target_exposure,actual_exposure,allocation_gap
        FROM shadow_book_performance
        WHERE portfolio_id=? AND performance_date=?""", (portfolio_id, as_of)).fetchone()
    if existing:
        attribution = pd.read_sql_query(
            """SELECT attribution_date,code,pnl_contribution,constraint_opportunity,transaction_cost
               FROM shadow_book_attribution WHERE portfolio_id=? AND attribution_date=? ORDER BY code""",
            conn, params=(portfolio_id, as_of))
        skips = pd.read_sql_query("""SELECT skip_date,code,reason,target_weight,target_notional
            FROM shadow_book_skips WHERE portfolio_id=? AND skip_date=? ORDER BY code""",
            conn, params=(portfolio_id, as_of))
        cash_drag = float(existing[5] or 0)
        return ShadowResult(
            portfolio_id, as_of, float(existing[0]), float(existing[1]), float(existing[2] or 0) * 100,
            float(existing[3] or 0) * 100, float(existing[4] or 0) * 100, cash_drag,
            max(cash_drag, 0), max(-cash_drag, 0), True,
            float(existing[6] or 0) * 100, float(existing[7] or 0) * 100,
            float(existing[8] or 0) * 100, pd.DataFrame(), skips, ranking, attribution,
        )
    prices, previous_prices = {}, {}
    for code in codes:
        rows = conn.execute("SELECT date,close FROM stock_prices WHERE code=? AND date<=? ORDER BY date DESC LIMIT 2",
                            (code, as_of)).fetchall()
        prices[code] = float(rows[0][1]); previous_prices[code] = float(rows[1][1]) if len(rows) > 1 else prices[code]
    benchmark_rows = conn.execute("SELECT date,close FROM stock_prices WHERE code=? AND date<=? ORDER BY date DESC LIMIT 2",
                                  (benchmark_code, as_of)).fetchall()
    benchmark_price = float(benchmark_rows[0][1]); previous_benchmark = float(benchmark_rows[1][1]) if len(benchmark_rows) > 1 else benchmark_price
    benchmark_daily_return = benchmark_price / previous_benchmark - 1

    now = datetime.now(timezone.utc).isoformat()
    account = conn.execute(
        """SELECT initial_capital,cash,strategy_version,config_hash
           FROM shadow_accounts WHERE portfolio_id=?""", (portfolio_id,)
    ).fetchone()
    if account is None:
        conn.execute("""INSERT INTO shadow_accounts(
            portfolio_id,initial_capital,cash,created_at,updated_at,
            strategy_version,config_hash,config_json,universe_hash)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (portfolio_id, initial_capital, initial_capital, now, now,
             STRATEGY_VERSION, config_hash, config_json, universe_hash))
        account = (initial_capital, initial_capital, STRATEGY_VERSION, config_hash)
    elif account[3] is None:
        conn.execute("""UPDATE shadow_accounts SET strategy_version=?,config_hash=?,
            config_json=?,universe_hash=?,updated_at=? WHERE portfolio_id=?""",
            (STRATEGY_VERSION, config_hash, config_json, universe_hash, now, portfolio_id))
    elif account[3] != config_hash:
        raise ValueError(
            f"포트폴리오 '{portfolio_id}'의 저장 설정과 현재 설정이 다릅니다. "
            "기존 성과를 보호하기 위해 실행을 중단했습니다. 새 --portfolio-id를 사용하세요."
        )
    initial_capital, cash = map(float, account[:2])
    position_rows = conn.execute("""SELECT code,quantity,average_price,target_weight,total_score
        FROM shadow_book_positions WHERE portfolio_id=?""", (portfolio_id,)).fetchall()
    positions = {row[0]: {"quantity": int(row[1]), "average_price": float(row[2]),
                          "target_weight": row[3], "total_score": row[4]} for row in position_rows}
    for code in codes:
        positions.setdefault(code, {"quantity": 0, "average_price": 0.0, "target_weight": 0.0, "total_score": 0.0})
    previous_cash = cash
    equity_before = cash + sum(positions[code]["quantity"] * prices[code] for code in codes)

    benchmark_history = pd.read_sql_query("SELECT close FROM stock_prices WHERE code=? AND date<=? ORDER BY date",
                                          conn, params=(benchmark_code, as_of))
    ma120 = benchmark_history["close"].tail(120).mean()
    exposure = .90 if benchmark_price > ma120 else .55
    eligible_ranking = ranking[ranking["eligible"]].copy()
    selected = eligible_ranking.head(min(top_n, len(eligible_ranking))).copy()
    if selected.empty:
        raise ValueError("투자 적격성 기준을 통과한 종목이 없습니다.")
    selected["raw"] = selected["total_score"].clip(lower=1) / selected["volatility_60"].clip(lower=5)
    selected_codes = set(selected["code"])
    uncapped = {row.code: row.raw / selected["raw"].sum() * exposure for row in selected.itertuples()}
    targets = _capped_weights(uncapped, industries, stock_cap, sector_cap, exposure)
    for code in codes:
        targets.setdefault(code, 0.0); uncapped.setdefault(code, 0.0)
    score_map = dict(zip(ranking["code"], ranking["total_score"]))

    prior_target_date = conn.execute(
        "SELECT MAX(target_date) FROM shadow_book_targets WHERE portfolio_id=?", (portfolio_id,)
    ).fetchone()[0]
    prior_targets = {}
    if prior_target_date:
        prior_targets = {row[0]: (row[1] or 0, row[2] or 0) for row in conn.execute(
            """SELECT code,uncapped_weight,target_weight FROM shadow_book_targets
               WHERE portfolio_id=? AND target_date=?""", (portfolio_id, prior_target_date))}
    attribution_rows, contribution_total = [], 0.0
    for code in codes:
        pnl = positions[code]["quantity"] * (prices[code] - previous_prices[code])
        contribution_total += pnl
        old_uncapped, old_capped = prior_targets.get(code, (0, 0))
        opportunity = equity_before * (old_uncapped - old_capped) * (prices[code] / previous_prices[code] - 1)
        attribution_rows.append({"attribution_date": as_of, "code": code,
                                 "pnl_contribution": round(pnl, 2),
                                 "constraint_opportunity": round(opportunity, 2), "transaction_cost": 0.0})

    commission, sell_tax, slippage = commission_pct / 100, sell_tax_pct / 100, slippage_pct / 100
    proposals, skips, costs_by_code = [], [], {code: 0.0 for code in codes}
    for row in ranking[~ranking["eligible"]].itertuples():
        skips.append({"skip_date": as_of, "code": row.code,
                      "reason": "INELIGIBLE: " + row.ineligible_reason,
                      "target_weight": 0.0, "target_notional": 0.0})
    target_qty = {code: math.floor(equity_before * targets[code] / prices[code]) for code in codes}
    # 매도 후 매수 순서. 실제 주문은 전송하지 않고 가상계좌에만 체결한다.
    for side in ("SELL", "BUY"):
        for code in codes:
            difference = target_qty[code] - positions[code]["quantity"]
            if (side == "SELL" and difference >= 0) or (side == "BUY" and difference <= 0):
                continue
            notional = abs(difference) * prices[code]
            if abs(targets[code] - positions[code]["quantity"] * prices[code] / max(equity_before, 1)) < rebalance_band:
                if code in selected_codes:
                    skips.append({"skip_date": as_of, "code": code, "reason": "WITHIN_REBALANCE_BAND",
                                  "target_weight": targets[code], "target_notional": notional})
                continue
            if notional < min_order:
                if code in selected_codes:
                    skips.append({"skip_date": as_of, "code": code, "reason": "BELOW_MIN_ORDER",
                                  "target_weight": targets[code], "target_notional": notional})
                continue
            qty = abs(difference)
            mid = prices[code]
            execution = mid * (1 - slippage if side == "SELL" else 1 + slippage)
            gross = qty * execution
            fee = gross * commission; tax = gross * sell_tax if side == "SELL" else 0.0
            slip_cost = qty * mid * slippage; estimated_cost = fee + tax + slip_cost
            if side == "BUY":
                qty = min(qty, math.floor(cash / (execution * (1 + commission))))
                if qty <= 0:
                    skips.append({"skip_date": as_of, "code": code, "reason": "INSUFFICIENT_CASH",
                                  "target_weight": targets[code], "target_notional": notional})
                    continue
                gross = qty * execution; fee = gross * commission; slip_cost = qty * mid * slippage
                estimated_cost = fee + slip_cost
                old_qty = positions[code]["quantity"]
                positions[code]["average_price"] = ((old_qty * positions[code]["average_price"] + gross + fee) /
                                                      (old_qty + qty))
                positions[code]["quantity"] += qty; cash -= gross + fee
            else:
                qty = min(qty, positions[code]["quantity"])
                gross = qty * execution; fee = gross * commission; tax = gross * sell_tax
                slip_cost = qty * mid * slippage; estimated_cost = fee + tax + slip_cost
                positions[code]["quantity"] -= qty; cash += gross - fee - tax
                if positions[code]["quantity"] == 0: positions[code]["average_price"] = 0.0
            costs_by_code[code] += estimated_cost
            proposals.append({"proposal_date": as_of, "code": code, "side": side, "quantity": qty,
                              "reference_price": mid, "estimated_cost": round(estimated_cost, 2),
                              "commission": round(fee, 2), "tax": round(tax, 2),
                              "slippage": round(slip_cost, 2),
                              "reason": "score_target_rebalance", "status": "SIMULATED_NO_ORDER"})

    accounted = {row["code"] for row in proposals} | {row["code"] for row in skips}
    for code in selected_codes - accounted:
        skips.append({"skip_date": as_of, "code": code, "reason": "NO_QUANTITY_CHANGE",
                      "target_weight": targets[code],
                      "target_notional": target_qty[code] * prices[code]})

    market_value = sum(positions[code]["quantity"] * prices[code] for code in codes)
    equity = cash + market_value
    previous_performance = conn.execute("""SELECT equity,benchmark_value,benchmark_price
        FROM shadow_book_performance WHERE portfolio_id=? ORDER BY performance_date DESC LIMIT 1""",
        (portfolio_id,)).fetchone()
    daily_return = equity / previous_performance[0] - 1 if previous_performance else 0.0
    cumulative_return = equity / initial_capital - 1
    benchmark_value = (previous_performance[1] * benchmark_price / previous_performance[2]
                       if previous_performance and previous_performance[2] else initial_capital)
    benchmark_return = benchmark_value / initial_capital - 1
    if previous_performance is None:
        cash_opportunity_cost = cash_defense = 0.0
    else:
        cash_opportunity_cost = max(previous_cash * benchmark_daily_return, 0.0)
        cash_defense = max(-previous_cash * benchmark_daily_return, 0.0)
    # DB 호환성을 위해 순 기회비용(상승 시 +, 하락 시 -)도 계속 저장한다.
    cash_drag = cash_opportunity_cost - cash_defense

    for row in attribution_rows:
        row["transaction_cost"] = round(costs_by_code[row["code"]], 2)
        conn.execute("INSERT OR REPLACE INTO shadow_book_attribution VALUES(?,?,?,?,?,?)",
                     (portfolio_id, *tuple(row.values())))
    for code in codes:
        conn.execute("INSERT OR REPLACE INTO shadow_book_targets VALUES(?,?,?,?,?,?,?)",
                     (portfolio_id, as_of, code, industries.get(code, "미분류"),
                      uncapped[code], targets[code], score_map.get(code)))
        state = positions[code]
        if state["quantity"] > 0:
            conn.execute("INSERT OR REPLACE INTO shadow_book_positions VALUES(?,?,?,?,?,?,?)",
                         (portfolio_id, code, state["quantity"], state["average_price"],
                          targets[code], score_map.get(code), now))
        else:
            conn.execute("DELETE FROM shadow_book_positions WHERE portfolio_id=? AND code=?",
                         (portfolio_id, code))
    for proposal in proposals:
        conn.execute("""INSERT INTO shadow_book_proposals(portfolio_id,proposal_date,code,side,
            quantity,reference_price,estimated_cost,commission,tax,slippage,reason,status)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (portfolio_id, *tuple(proposal.values())))
    for skipped in skips:
        conn.execute("INSERT OR REPLACE INTO shadow_book_skips VALUES(?,?,?,?,?,?)",
                     (portfolio_id, *tuple(skipped.values())))
    conn.execute("UPDATE shadow_accounts SET cash=?,updated_at=? WHERE portfolio_id=?",
                 (cash, now, portfolio_id))
    target_exposure = sum(targets.values())
    actual_exposure = market_value / max(equity, 1)
    allocation_gap = target_exposure - actual_exposure
    conn.execute("""INSERT OR REPLACE INTO shadow_book_performance(
        portfolio_id,performance_date,equity,cash,market_value,daily_return,cumulative_return,
        benchmark_value,benchmark_return,benchmark_price,cash_drag,target_exposure,
        actual_exposure,allocation_gap) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (portfolio_id, as_of, equity, cash, market_value, daily_return, cumulative_return,
         benchmark_value, benchmark_return, benchmark_price, cash_drag, target_exposure,
         actual_exposure, allocation_gap))
    conn.commit()
    return ShadowResult(portfolio_id, as_of, round(equity, 2), round(cash, 2), round(daily_return * 100, 4),
                        round(cumulative_return * 100, 4), round(benchmark_return * 100, 4),
                        round(cash_drag, 2), round(cash_opportunity_cost, 2),
                        round(cash_defense, 2), False, round(target_exposure * 100, 4),
                        round(actual_exposure * 100, 4), round(allocation_gap * 100, 4),
                        pd.DataFrame(proposals), pd.DataFrame(skips), ranking,
                        pd.DataFrame(attribution_rows))
