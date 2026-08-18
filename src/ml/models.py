from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.ml.feature_store import FEATURE_COLUMNS


@dataclass(frozen=True)
class Evaluation:
    model_name: str
    sample_count: int
    positive_rate: float
    roc_auc: float | None
    accuracy: float
    brier: float
    mean_excess_return: float
    top_quintile_excess_return: float


def _model_factories() -> dict[str, callable]:
    return {
        "logistic_regression": lambda: Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
        ]),
        "hist_gradient_boosting": lambda: Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("model", HistGradientBoostingClassifier(
                learning_rate=0.05, max_iter=200, max_leaf_nodes=15,
                l2_regularization=1.0, random_state=42)),
        ]),
    }


def load_ml_dataset(conn: sqlite3.Connection, horizon: int,
                    benchmark_code: str = "069500") -> pd.DataFrame:
    fields = ",".join(f"f.{name}" for name in FEATURE_COLUMNS)
    data = pd.read_sql_query(
        f"""SELECT f.code,f.feature_date,f.industry,f.close,f.volume,{fields},
                   l.positive_excess,l.excess_return,l.forward_return,
                   l.benchmark_forward_return,
                   l.max_drawdown,l.label_available_at
            FROM ml_features f JOIN ml_labels l
              ON l.code=f.code AND l.feature_date=f.feature_date
             AND l.benchmark_code=f.benchmark_code
            WHERE f.benchmark_code=? AND l.horizon=?
              AND l.positive_excess IS NOT NULL
            ORDER BY f.feature_date,f.code""", conn,
        params=(benchmark_code, horizon))
    for column in FEATURE_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def _evaluate(name: str, model, frame: pd.DataFrame) -> tuple[Evaluation, pd.DataFrame]:
    probabilities = model.predict_proba(frame[FEATURE_COLUMNS])[:, 1]
    predictions = (probabilities >= .5).astype(int)
    target = frame["positive_excess"].astype(int).to_numpy()
    auc = None if len(np.unique(target)) < 2 else float(roc_auc_score(target, probabilities))
    output = frame[["code", "feature_date", "positive_excess", "excess_return",
                    "forward_return", "max_drawdown"]].copy()
    output["model_name"] = name
    output["probability"] = probabilities
    output["prediction"] = predictions
    cutoff = float(np.quantile(probabilities, .8))
    top = output.loc[output["probability"] >= cutoff, "excess_return"]
    evaluation = Evaluation(
        model_name=name, sample_count=len(frame), positive_rate=float(target.mean()),
        roc_auc=auc, accuracy=float(accuracy_score(target, predictions)),
        brier=float(brier_score_loss(target, probabilities)),
        mean_excess_return=float(output["excess_return"].mean()),
        top_quintile_excess_return=float(top.mean()) if not top.empty else float("nan"),
    )
    return evaluation, output


def _date_boundaries(data: pd.DataFrame, validation_days: int, test_days: int):
    dates = np.array(sorted(data["feature_date"].unique()))
    required = validation_days + test_days + 252
    if len(dates) < required:
        raise ValueError(f"ML 학습 거래일이 부족합니다: {len(dates)}일 (최소 {required}일 필요)")
    return dates[-(validation_days + test_days)], dates[-test_days]


def train_baselines(conn: sqlite3.Connection, horizon: int = 20,
                    benchmark_code: str = "069500", validation_days: int = 126,
                    test_days: int = 126, artifact_path: str = "models/baseline_h20.joblib",
                    output_prefix: str = "ml_baseline") -> dict:
    data = load_ml_dataset(conn, horizon, benchmark_code)
    if data.empty:
        raise ValueError("학습 데이터가 없습니다. build-feature-store를 먼저 실행하세요.")
    validation_start, test_start = _date_boundaries(data, validation_days, test_days)
    train = data[(data["feature_date"] < validation_start) &
                 (data["label_available_at"] < validation_start)]
    validation = data[(data["feature_date"] >= validation_start) &
                      (data["feature_date"] < test_start) &
                      (data["label_available_at"] < test_start)]
    test = data[data["feature_date"] >= test_start]
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("시간순 학습·검증·테스트 분리에 필요한 표본이 부족합니다.")
    factories = _model_factories()
    validation_results: list[Evaluation] = []
    validation_predictions = []
    fitted = {}
    for name, factory in factories.items():
        model = factory()
        model.fit(train[FEATURE_COLUMNS], train["positive_excess"].astype(int))
        evaluation, predictions = _evaluate(name, model, validation)
        validation_results.append(evaluation)
        validation_predictions.append(predictions.assign(split="validation"))
        fitted[name] = model
    selected = min(validation_results, key=lambda item: (item.brier, -(item.roc_auc or 0))).model_name
    development = data[(data["feature_date"] < test_start) &
                       (data["label_available_at"] < test_start)]
    final_models = {}
    test_results: list[Evaluation] = []
    test_predictions = []
    for name, factory in factories.items():
        model = factory()
        model.fit(development[FEATURE_COLUMNS], development["positive_excess"].astype(int))
        evaluation, predictions = _evaluate(name, model, test)
        test_results.append(evaluation)
        test_predictions.append(predictions.assign(split="lockbox_test"))
        final_models[name] = model
    artifact = Path(artifact_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "horizon": horizon, "benchmark_code": benchmark_code,
        "feature_columns": FEATURE_COLUMNS, "selected_model": selected,
        "trained_through": str(development["feature_date"].max()), "models": final_models,
    }
    joblib.dump(bundle, artifact)
    prefix = Path(output_prefix)
    metrics_rows = ([{"split": "validation", **asdict(item)} for item in validation_results] +
                    [{"split": "lockbox_test", **asdict(item)} for item in test_results])
    metrics = pd.DataFrame(metrics_rows)
    metrics.to_csv(prefix.with_name(prefix.name + "_metrics.csv"), index=False, encoding="utf-8-sig")
    pd.concat([*validation_predictions, *test_predictions], ignore_index=True).to_csv(
        prefix.with_name(prefix.name + "_predictions.csv"), index=False, encoding="utf-8-sig")
    metadata = {
        "selected_model": selected, "horizon": horizon,
        "train_start": str(train["feature_date"].min()), "train_end": str(train["feature_date"].max()),
        "validation_start": str(validation["feature_date"].min()),
        "validation_end": str(validation["feature_date"].max()),
        "test_start": str(test["feature_date"].min()), "test_end": str(test["feature_date"].max()),
        "feature_count": len(FEATURE_COLUMNS), "sample_count": len(data),
        "artifact_path": str(artifact), "metrics": metrics_rows,
    }
    prefix.with_name(prefix.name + "_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    selected_test = next(item for item in test_results if item.model_name == selected)
    conn.execute("""INSERT INTO ml_model_runs(
        created_at,model_name,horizon,train_start,train_end,validation_start,validation_end,
        test_start,test_end,feature_count,sample_count,roc_auc,accuracy,brier,artifact_path,metadata_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        datetime.now(timezone.utc).isoformat(), selected, horizon, metadata["train_start"],
        metadata["train_end"], metadata["validation_start"], metadata["validation_end"],
        metadata["test_start"], metadata["test_end"], len(FEATURE_COLUMNS), len(data),
        selected_test.roc_auc, selected_test.accuracy, selected_test.brier,
        str(artifact), json.dumps(metadata, ensure_ascii=False)))
    conn.commit()
    return metadata


def walk_forward_baselines(conn: sqlite3.Connection, horizon: int = 20,
                           benchmark_code: str = "069500", min_train_days: int = 504,
                           test_days: int = 126, output_csv: str = "ml_walk_forward.csv") -> pd.DataFrame:
    data = load_ml_dataset(conn, horizon, benchmark_code)
    dates = np.array(sorted(data["feature_date"].unique()))
    if len(dates) < min_train_days + test_days:
        raise ValueError("워크포워드 검증 거래일이 부족합니다.")
    rows = []
    for test_offset in range(min_train_days, len(dates), test_days):
        test_dates = dates[test_offset:min(test_offset + test_days, len(dates))]
        if len(test_dates) < max(20, test_days // 3):
            continue
        test_start, test_end = test_dates[0], test_dates[-1]
        train = data[(data["feature_date"] < test_start) &
                     (data["label_available_at"] < test_start)]
        test = data[data["feature_date"].isin(test_dates)]
        if train.empty or test.empty:
            continue
        for name, factory in _model_factories().items():
            model = factory()
            model.fit(train[FEATURE_COLUMNS], train["positive_excess"].astype(int))
            evaluation, _ = _evaluate(name, model, test)
            rows.append({"fold": len(rows) // len(_model_factories()) + 1,
                         "train_start": train["feature_date"].min(),
                         "train_end": train["feature_date"].max(),
                         "test_start": test_start, "test_end": test_end,
                         **asdict(evaluation)})
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("생성 가능한 워크포워드 구간이 없습니다.")
    result.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return result


def predict_latest(conn: sqlite3.Connection, artifact_path: str,
                   output_csv: str = "ml_latest_predictions.csv") -> pd.DataFrame:
    bundle = joblib.load(artifact_path)
    benchmark_code = bundle["benchmark_code"]
    data = pd.read_sql_query(
        """SELECT f.* FROM ml_features f
           WHERE f.benchmark_code=? AND f.feature_date=(
             SELECT MAX(x.feature_date) FROM ml_features x
             WHERE x.code=f.code AND x.benchmark_code=f.benchmark_code)
           ORDER BY f.code""", conn, params=(benchmark_code,))
    if data.empty:
        raise ValueError("예측할 Feature Store 행이 없습니다.")
    output = data[["code", "feature_date", "industry", "close",
                   "financial_fiscal_year", "financial_disclosed_at"]].copy()
    for name, model in bundle["models"].items():
        output[f"probability_{name}"] = model.predict_proba(data[bundle["feature_columns"]])[:, 1]
    selected = bundle["selected_model"]
    output["selected_model"] = selected
    output["probability"] = output[f"probability_{selected}"]
    output["rank"] = output["probability"].rank(method="min", ascending=False).astype(int)
    output = output.sort_values(["rank", "code"])
    output.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return output
