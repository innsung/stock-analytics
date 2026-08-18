import sqlite3

import numpy as np
import pandas as pd
import pytest

from database.database import connect, upsert_financials, upsert_prices
from src.ml.feature_store import (FEATURE_COLUMNS, build_feature_store,
                                  point_in_time_annual_financials)
from src.ml.models import predict_latest, train_baselines, walk_forward_baselines


def _financial_rows(code, year, disclosed_at, scale):
    values = [
        ("IS", "ifrs-full_Revenue", "매출액", 1_000 * scale),
        ("IS", "dart_OperatingIncomeLoss", "영업이익", 100 * scale),
        ("IS", "ifrs-full_ProfitLoss", "당기순이익", 80 * scale),
        ("IS", "ifrs-full_BasicEarningsLossPerShare", "기본주당이익", 800 * scale),
        ("BS", "ifrs-full_Assets", "자산총계", 2_000 * scale),
        ("BS", "ifrs-full_Liabilities", "부채총계", 800 * scale),
        ("BS", "ifrs-full_Equity", "자본총계", 1_200 * scale),
        ("CF", "ifrs-full_CashFlowsFromUsedInOperatingActivities", "영업활동현금흐름", 90 * scale),
    ]
    return [(code, year, "11011", "CFS", statement, account_id, name, amount,
             "KRW", order, disclosed_at, "DART")
            for order, (statement, account_id, name, amount) in enumerate(values)]


def test_financial_facts_use_disclosure_date(tmp_path):
    conn = connect(tmp_path / "test.db")
    upsert_financials(conn, _financial_rows("005930", 2022, "20230331", 1.0))
    upsert_financials(conn, _financial_rows("005930", 2023, "20240331", 1.1))
    facts = point_in_time_annual_financials(conn, "005930")
    assert facts["financial_disclosed_at"].tolist() == ["20230331", "20240331"]
    assert facts.iloc[1]["revenue_growth"] == 10.0
    assert facts.iloc[1]["reported_eps"] == pytest.approx(880.0)
    assert facts.iloc[1]["estimated_bps"] > 0


def test_financial_facts_fall_back_to_ofs_when_cfs_is_missing(tmp_path):
    conn = connect(tmp_path / "test.db")
    rows = [tuple("OFS" if index == 3 else value for index, value in enumerate(row))
            for row in _financial_rows("105560", 2021, "20220331", 1.0)]
    upsert_financials(conn, rows)
    facts = point_in_time_annual_financials(conn, "105560")
    assert facts.iloc[0]["financial_fs_div"] == "OFS"
    assert facts.iloc[0]["reported_eps"] == 800
    conn.close()


def test_feature_store_and_labels_are_point_in_time(tmp_path):
    conn = connect(tmp_path / "test.db")
    dates = pd.bdate_range("2022-01-03", periods=700)
    for code, slope in (("005930", .08), ("069500", .05)):
        rows = []
        for index, day in enumerate(dates):
            close = 50_000 + index * slope * 100 + np.sin(index / 9) * 500
            rows.append((code, day.strftime("%Y%m%d"), close - 50, close + 100,
                         close - 100, close, 1_000_000 + index, "TEST"))
        upsert_prices(conn, rows)
    upsert_financials(conn, _financial_rows("005930", 2022, "20230331", 1.0))
    features, labels = build_feature_store(conn, ["005930"], {"005930": "반도체"}, "069500")
    assert features > 400
    assert labels == (700 - 5) + (700 - 20) + (700 - 60)
    before = conn.execute("""SELECT financial_fiscal_year FROM ml_features
        WHERE code='005930' AND feature_date<'20230331'
        ORDER BY feature_date DESC LIMIT 1""").fetchone()
    after = conn.execute("""SELECT financial_fiscal_year,historical_per FROM ml_features
        WHERE code='005930' AND feature_date>='20230331'
        ORDER BY feature_date LIMIT 1""").fetchone()
    assert before[0] is None
    assert after[0] == 2022
    assert after[1] is not None
    label = conn.execute("""SELECT feature_date,label_available_at FROM ml_labels
        WHERE code='005930' AND horizon=20 ORDER BY feature_date LIMIT 1""").fetchone()
    assert label[1] > label[0]


def _seed_ml_rows(conn: sqlite3.Connection, periods=520, codes=4):
    dates = pd.bdate_range("2023-01-02", periods=periods)
    feature_columns = [row[1] for row in conn.execute("PRAGMA table_info(ml_features)")]
    label_columns = [row[1] for row in conn.execute("PRAGMA table_info(ml_labels)")]
    rng = np.random.default_rng(42)
    for code_index in range(codes):
        code = f"{code_index + 1:06d}"
        signal = rng.normal(size=periods)
        for index, day in enumerate(dates):
            feature = {column: None for column in feature_columns}
            feature.update({"code": code, "feature_date": day.strftime("%Y%m%d"),
                            "benchmark_code": "069500", "industry": "테스트",
                            "close": 10_000 + index, "volume": 100_000,
                            "generated_at": "2025-01-01T00:00:00+00:00"})
            for feature_index, column in enumerate(FEATURE_COLUMNS):
                feature[column] = signal[index] + feature_index * .01
            conn.execute(f"INSERT INTO ml_features({','.join(feature_columns)}) VALUES({','.join('?' for _ in feature_columns)})",
                         tuple(feature[column] for column in feature_columns))
            if index + 20 < periods:
                label = {column: None for column in label_columns}
                excess = signal[index] + rng.normal(scale=.7)
                label.update({"code": code, "feature_date": day.strftime("%Y%m%d"),
                              "benchmark_code": "069500", "horizon": 20,
                              "forward_return": excess, "benchmark_forward_return": 0,
                              "excess_return": excess, "positive_excess": int(excess > 0),
                              "max_drawdown": min(excess, 0),
                              "label_available_at": dates[index + 20].strftime("%Y%m%d"),
                              "generated_at": "2025-01-01T00:00:00+00:00"})
                conn.execute(f"INSERT INTO ml_labels({','.join(label_columns)}) VALUES({','.join('?' for _ in label_columns)})",
                             tuple(label[column] for column in label_columns))
    conn.commit()


def test_baseline_train_walk_forward_and_predict(tmp_path):
    conn = connect(tmp_path / "test.db")
    _seed_ml_rows(conn)
    artifact = tmp_path / "model.joblib"
    metadata = train_baselines(conn, validation_days=60, test_days=60,
                               artifact_path=str(artifact),
                               output_prefix=str(tmp_path / "baseline"))
    assert artifact.exists()
    assert metadata["selected_model"] in {"logistic_regression", "hist_gradient_boosting"}
    predictions = predict_latest(conn, str(artifact), str(tmp_path / "latest.csv"))
    assert len(predictions) == 4
    assert predictions["probability"].between(0, 1).all()
    folds = walk_forward_baselines(conn, min_train_days=300, test_days=60,
                                   output_csv=str(tmp_path / "walk.csv"))
    assert set(folds["model_name"]) == {"logistic_regression", "hist_gradient_boosting"}
