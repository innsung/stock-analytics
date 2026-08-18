import sqlite3
from pathlib import Path
from typing import Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_prices (
    code TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL,
    close REAL NOT NULL, volume INTEGER, source TEXT NOT NULL,
    PRIMARY KEY (code, date)
);
CREATE TABLE IF NOT EXISTS financial_statements (
    code TEXT NOT NULL, fiscal_year INTEGER NOT NULL, report_code TEXT NOT NULL,
    fs_div TEXT NOT NULL, sj_div TEXT NOT NULL, account_id TEXT NOT NULL,
    account_name TEXT NOT NULL, amount REAL, currency TEXT, account_order INTEGER,
    disclosed_at TEXT, source TEXT NOT NULL,
    PRIMARY KEY (code, fiscal_year, report_code, fs_div, sj_div, account_id, account_name)
);
CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, created_at TEXT NOT NULL,
    strategy TEXT NOT NULL, total_return REAL NOT NULL, mdd REAL NOT NULL,
    win_rate REAL NOT NULL, trades INTEGER NOT NULL,
    benchmark_return REAL, excess_return REAL, cagr REAL, sharpe REAL,
    profit_factor REAL, total_cost REAL
);
CREATE TABLE IF NOT EXISTS valuation_snapshots (
    code TEXT NOT NULL, snapshot_date TEXT NOT NULL, price REAL, market_cap REAL,
    per REAL, pbr REAL, eps REAL, bps REAL, dividend_yield REAL, source TEXT NOT NULL,
    PRIMARY KEY(code, snapshot_date)
);
CREATE TABLE IF NOT EXISTS valuation_snapshot_meta (
    code TEXT NOT NULL, snapshot_date TEXT NOT NULL, known_at TEXT NOT NULL,
    source TEXT NOT NULL, PRIMARY KEY(code, snapshot_date)
);
CREATE TABLE IF NOT EXISTS shadow_account (
    id INTEGER PRIMARY KEY CHECK(id=1), initial_capital REAL NOT NULL,
    cash REAL NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_positions (
    code TEXT PRIMARY KEY, quantity INTEGER NOT NULL, average_price REAL NOT NULL,
    target_weight REAL, total_score REAL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, proposal_date TEXT NOT NULL, code TEXT NOT NULL,
    side TEXT NOT NULL, quantity INTEGER NOT NULL, reference_price REAL NOT NULL,
    estimated_cost REAL NOT NULL, commission REAL, tax REAL, slippage REAL,
    reason TEXT, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_performance (
    performance_date TEXT PRIMARY KEY, equity REAL NOT NULL, cash REAL NOT NULL,
    market_value REAL NOT NULL, daily_return REAL, cumulative_return REAL,
    benchmark_value REAL, benchmark_return REAL, benchmark_price REAL, cash_drag REAL
);
CREATE TABLE IF NOT EXISTS shadow_targets (
    target_date TEXT NOT NULL, code TEXT NOT NULL, industry TEXT,
    uncapped_weight REAL, target_weight REAL, total_score REAL,
    PRIMARY KEY(target_date, code)
);
CREATE TABLE IF NOT EXISTS shadow_attribution (
    attribution_date TEXT NOT NULL, code TEXT NOT NULL, pnl_contribution REAL,
    constraint_opportunity REAL, transaction_cost REAL,
    PRIMARY KEY(attribution_date, code)
);
CREATE TABLE IF NOT EXISTS shadow_accounts (
    portfolio_id TEXT PRIMARY KEY, initial_capital REAL NOT NULL,
    cash REAL NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    strategy_version TEXT, config_hash TEXT, config_json TEXT, universe_hash TEXT
);
CREATE TABLE IF NOT EXISTS shadow_book_positions (
    portfolio_id TEXT NOT NULL, code TEXT NOT NULL, quantity INTEGER NOT NULL,
    average_price REAL NOT NULL, target_weight REAL, total_score REAL,
    updated_at TEXT NOT NULL, PRIMARY KEY(portfolio_id, code)
);
CREATE TABLE IF NOT EXISTS shadow_book_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, portfolio_id TEXT NOT NULL,
    proposal_date TEXT NOT NULL, code TEXT NOT NULL, side TEXT NOT NULL,
    quantity INTEGER NOT NULL, reference_price REAL NOT NULL,
    estimated_cost REAL NOT NULL, commission REAL, tax REAL, slippage REAL,
    reason TEXT, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_book_performance (
    portfolio_id TEXT NOT NULL, performance_date TEXT NOT NULL,
    equity REAL NOT NULL, cash REAL NOT NULL, market_value REAL NOT NULL,
    daily_return REAL, cumulative_return REAL, benchmark_value REAL,
    benchmark_return REAL, benchmark_price REAL, cash_drag REAL,
    PRIMARY KEY(portfolio_id, performance_date)
);
CREATE TABLE IF NOT EXISTS shadow_book_targets (
    portfolio_id TEXT NOT NULL, target_date TEXT NOT NULL, code TEXT NOT NULL,
    industry TEXT, uncapped_weight REAL, target_weight REAL, total_score REAL,
    PRIMARY KEY(portfolio_id, target_date, code)
);
CREATE TABLE IF NOT EXISTS shadow_book_attribution (
    portfolio_id TEXT NOT NULL, attribution_date TEXT NOT NULL, code TEXT NOT NULL,
    pnl_contribution REAL, constraint_opportunity REAL, transaction_cost REAL,
    PRIMARY KEY(portfolio_id, attribution_date, code)
);
CREATE TABLE IF NOT EXISTS shadow_book_skips (
    portfolio_id TEXT NOT NULL, skip_date TEXT NOT NULL, code TEXT NOT NULL,
    reason TEXT NOT NULL, target_weight REAL, target_notional REAL,
    PRIMARY KEY(portfolio_id, skip_date, code, reason)
);
CREATE TABLE IF NOT EXISTS daily_run_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, portfolio_id TEXT NOT NULL,
    started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
    evaluation_date TEXT, price_rows INTEGER DEFAULT 0,
    valuation_rows INTEGER DEFAULT 0, error_count INTEGER DEFAULT 0,
    message TEXT
);
CREATE TABLE IF NOT EXISTS ml_features (
    code TEXT NOT NULL, feature_date TEXT NOT NULL, benchmark_code TEXT NOT NULL,
    industry TEXT, close REAL, volume REAL,
    return_5 REAL, return_20 REAL, return_60 REAL, return_126 REAL,
    relative_20 REAL, relative_60 REAL, volatility_20 REAL, volatility_60 REAL,
    rsi_14 REAL, atr_14_pct REAL, ma_20_gap REAL, ma_60_gap REAL,
    liquidity_20 REAL, benchmark_return_20 REAL, benchmark_ma_120_gap REAL,
    benchmark_volatility_60 REAL, market_regime INTEGER,
    revenue_growth REAL, operating_margin REAL, roe REAL, debt_ratio REAL,
    operating_cash_flow_positive REAL, reported_eps REAL, estimated_bps REAL,
    historical_per REAL, historical_pbr REAL, financial_fiscal_year INTEGER,
    financial_disclosed_at TEXT, financial_fs_div TEXT, valuation_per REAL, valuation_pbr REAL,
    valuation_eps REAL, valuation_bps REAL, valuation_snapshot_date TEXT,
    valuation_known_at TEXT, generated_at TEXT NOT NULL,
    PRIMARY KEY(code, feature_date, benchmark_code)
);
CREATE TABLE IF NOT EXISTS ml_labels (
    code TEXT NOT NULL, feature_date TEXT NOT NULL, benchmark_code TEXT NOT NULL,
    horizon INTEGER NOT NULL, forward_return REAL, benchmark_forward_return REAL,
    excess_return REAL, positive_excess INTEGER, max_drawdown REAL,
    label_available_at TEXT, generated_at TEXT NOT NULL,
    PRIMARY KEY(code, feature_date, benchmark_code, horizon)
);
CREATE TABLE IF NOT EXISTS ml_model_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
    model_name TEXT NOT NULL, horizon INTEGER NOT NULL, train_start TEXT,
    train_end TEXT, validation_start TEXT, validation_end TEXT,
    test_start TEXT, test_end TEXT, feature_count INTEGER, sample_count INTEGER,
    roc_auc REAL, accuracy REAL, brier REAL, artifact_path TEXT, metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS ml_lockbox_registry (
    benchmark_code TEXT NOT NULL, horizon INTEGER NOT NULL,
    diagnostic_version INTEGER NOT NULL, lockbox_start TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    PRIMARY KEY(benchmark_code, horizon, diagnostic_version)
);
CREATE TABLE IF NOT EXISTS ml_research_cutoff_registry (
    benchmark_code TEXT NOT NULL, horizon INTEGER NOT NULL,
    diagnostic_version INTEGER NOT NULL, seen_through TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(benchmark_code, horizon, diagnostic_version)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate_financial_schema(conn)
    conn.executescript(SCHEMA)
    _migrate_shadow_books(conn)
    _migrate_shadow_account_schema(conn)
    _migrate_shadow_book_schema(conn)
    _migrate_disclosure_date(conn)
    _migrate_backtest_schema(conn)
    _migrate_ml_feature_schema(conn)
    return conn


def _migrate_ml_feature_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(ml_features)")}
    changed = False
    if "financial_fs_div" not in columns:
        conn.execute("ALTER TABLE ml_features ADD COLUMN financial_fs_div TEXT")
        changed = True
    if "valuation_known_at" not in columns:
        conn.execute("ALTER TABLE ml_features ADD COLUMN valuation_known_at TEXT")
        changed = True
    conn.execute("""CREATE TABLE IF NOT EXISTS valuation_snapshot_meta (
        code TEXT NOT NULL, snapshot_date TEXT NOT NULL, known_at TEXT NOT NULL,
        source TEXT NOT NULL, PRIMARY KEY(code, snapshot_date))""")
    if changed:
        conn.commit()


def _migrate_shadow_book_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(shadow_book_performance)")}
    for name in ("target_exposure", "actual_exposure", "allocation_gap"):
        if name not in columns:
            conn.execute(f"ALTER TABLE shadow_book_performance ADD COLUMN {name} REAL")
    conn.execute("""UPDATE shadow_book_performance
        SET actual_exposure=CASE WHEN equity>0 THEN market_value/equity ELSE 0 END
        WHERE actual_exposure IS NULL""")
    conn.execute("""UPDATE shadow_book_performance
        SET target_exposure=actual_exposure WHERE target_exposure IS NULL""")
    conn.execute("""UPDATE shadow_book_performance
        SET allocation_gap=target_exposure-actual_exposure WHERE allocation_gap IS NULL""")
    # 계좌 개설일에는 전일 보유현금이라는 비교 기준이 없으므로 현금효과는 0이다.
    conn.execute("""UPDATE shadow_book_performance AS p SET cash_drag=0
        WHERE performance_date=(SELECT MIN(x.performance_date)
            FROM shadow_book_performance x WHERE x.portfolio_id=p.portfolio_id)""")
    conn.commit()


def _migrate_shadow_account_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(shadow_accounts)")}
    for name in ("strategy_version", "config_hash", "config_json", "universe_hash"):
        if name not in columns:
            conn.execute(f"ALTER TABLE shadow_accounts ADD COLUMN {name} TEXT")
    conn.commit()


def _migrate_shadow_books(conn: sqlite3.Connection) -> None:
    """단일 그림자 계좌 기록을 default 포트폴리오로 한 번만 복사한다."""
    if conn.execute("SELECT 1 FROM shadow_accounts WHERE portfolio_id='default'").fetchone():
        return
    account = conn.execute(
        "SELECT initial_capital,cash,created_at,updated_at FROM shadow_account WHERE id=1"
    ).fetchone()
    if account is None:
        return
    conn.execute("""INSERT INTO shadow_accounts(
        portfolio_id,initial_capital,cash,created_at,updated_at)
        VALUES('default',?,?,?,?)""", account)
    conn.execute("""INSERT OR IGNORE INTO shadow_book_positions
        SELECT 'default',code,quantity,average_price,target_weight,total_score,updated_at
        FROM shadow_positions""")
    conn.execute("""INSERT INTO shadow_book_proposals(
        portfolio_id,proposal_date,code,side,quantity,reference_price,estimated_cost,
        commission,tax,slippage,reason,status)
        SELECT 'default',proposal_date,code,side,quantity,reference_price,estimated_cost,
        commission,tax,slippage,reason,status FROM shadow_proposals""")
    conn.execute("""INSERT OR IGNORE INTO shadow_book_performance(
        portfolio_id,performance_date,equity,cash,market_value,daily_return,
        cumulative_return,benchmark_value,benchmark_return,benchmark_price,cash_drag)
        SELECT 'default',performance_date,equity,cash,market_value,daily_return,
        cumulative_return,benchmark_value,benchmark_return,benchmark_price,cash_drag
        FROM shadow_performance""")
    conn.execute("""INSERT OR IGNORE INTO shadow_book_targets
        SELECT 'default',target_date,code,industry,uncapped_weight,target_weight,total_score
        FROM shadow_targets""")
    conn.execute("""INSERT OR IGNORE INTO shadow_book_attribution
        SELECT 'default',attribution_date,code,pnl_contribution,constraint_opportunity,
        transaction_cost FROM shadow_attribution""")
    conn.commit()


def _migrate_disclosure_date(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(financial_statements)")}
    if "disclosed_at" not in columns:
        conn.execute("ALTER TABLE financial_statements ADD COLUMN disclosed_at TEXT")
        conn.commit()


def _migrate_backtest_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(backtest_runs)")}
    additions = {
        "benchmark_return": "REAL", "excess_return": "REAL", "cagr": "REAL",
        "sharpe": "REAL", "profit_factor": "REAL", "total_cost": "REAL",
    }
    for name, sql_type in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE backtest_runs ADD COLUMN {name} {sql_type}")
    conn.commit()


def _migrate_financial_schema(conn: sqlite3.Connection) -> None:
    """구형 계정명 전용 표를 보존하고 표준 계정 ID 기반 표로 전환한다."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='financial_statements'"
    ).fetchone()
    if not exists:
        return
    columns = {row[1] for row in conn.execute("PRAGMA table_info(financial_statements)")}
    if {"account_id", "fs_div", "sj_div"}.issubset(columns):
        return
    legacy_name = "financial_statements_legacy"
    suffix = 1
    while conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (legacy_name,)
    ).fetchone():
        legacy_name = f"financial_statements_legacy_{suffix}"
        suffix += 1
    conn.execute(f'ALTER TABLE financial_statements RENAME TO "{legacy_name}"')
    conn.commit()


def upsert_prices(conn: sqlite3.Connection, rows: Iterable[tuple]) -> None:
    conn.executemany(
        """INSERT INTO stock_prices(code,date,open,high,low,close,volume,source)
        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(code,date) DO UPDATE SET
        open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
        volume=excluded.volume, source=excluded.source""",
        rows,
    )
    conn.commit()


def upsert_financials(conn: sqlite3.Connection, rows: Iterable[tuple]) -> None:
    conn.executemany(
        """INSERT INTO financial_statements(
            code,fiscal_year,report_code,fs_div,sj_div,account_id,account_name,
            amount,currency,account_order,disclosed_at,source
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(code,fiscal_year,report_code,fs_div,sj_div,account_id,account_name)
        DO UPDATE SET amount=excluded.amount, currency=excluded.currency,
                      account_order=excluded.account_order, disclosed_at=excluded.disclosed_at,
                      source=excluded.source""",
        rows,
    )
    conn.commit()
