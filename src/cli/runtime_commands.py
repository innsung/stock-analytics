from __future__ import annotations

import sqlite3

import pandas as pd


RUNTIME_COMMANDS = frozenset({
    "shadow-list",
    "daily-status",
    "ml-readiness",
    "shadow-report",
    "daily-shadow",
    "build-feature-store",
    "ml-train",
    "ml-walk-forward",
    "ml-predict",
})


def run_runtime_command(
    conn: sqlite3.Connection,
    settings,
    args,
    *,
    resolve_codes,
    print_shadow_report,
    execute_daily_shadow,
) -> None:
    """Run daily operations and baseline ML commands."""
    if args.command not in RUNTIME_COMMANDS:
        raise ValueError(f"지원하지 않는 운영 명령입니다: {args.command}")

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
        args.codes, _ = resolve_codes(args)
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
        from src.ml.feature_store import build_feature_store

        args.codes, mapping = resolve_codes(args)
        feature_count, label_count = build_feature_store(
            conn, args.codes, mapping, args.benchmark_code)
        print(f"Feature Store 저장: {feature_count:,}행")
        print(f"미래수익 라벨 저장: {label_count:,}행 (5·20·60거래일)")
        print("시점 규칙: 각 행에는 feature_date까지 공시·관측된 정보만 사용")
    elif args.command == "ml-train":
        from src.ml.models import train_baselines

        metadata = train_baselines(
            conn, args.horizon, args.benchmark_code, args.validation_days,
            args.test_days, args.artifact, args.output_prefix)
        print(f"기준 ML 학습 완료: {metadata['selected_model']}")
        print(f"학습/검증/봉인시험: {metadata['train_start']}~{metadata['train_end']} / "
              f"{metadata['validation_start']}~{metadata['validation_end']} / "
              f"{metadata['test_start']}~{metadata['test_end']}")
        print(f"모델 저장: {metadata['artifact_path']}")
    elif args.command == "ml-walk-forward":
        from src.ml.models import walk_forward_baselines

        result = walk_forward_baselines(
            conn, args.horizon, args.benchmark_code, args.min_train_days,
            args.test_days, args.output_csv)
        summary = result.groupby("model_name")[["roc_auc", "accuracy", "brier",
            "top_quintile_excess_return"]].mean(numeric_only=True)
        print("[ML 워크포워드 평균]")
        print(summary.to_string())
        print(f"구간별 결과 저장: {args.output_csv}")
    elif args.command == "ml-predict":
        from src.ml.models import predict_latest

        predictions = predict_latest(conn, args.artifact, args.output_csv)
        print(predictions[["rank", "code", "feature_date", "probability",
                           "selected_model"]].to_string(index=False))
        print(f"최신 예측 저장: {args.output_csv}")
