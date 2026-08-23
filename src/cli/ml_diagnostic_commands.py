from __future__ import annotations

from pathlib import Path

from src.ml.persistent_data_v321 import assert_persistent_data_v321
from src.ml.result_bundle_v321 import create_result_bundle_v321


def run_ml_diagnostic_command(conn, settings, args) -> None:
    from src.ml.diagnostics_v321 import run_ml_diagnostics_v321

    try:
        health = assert_persistent_data_v321(conn, settings.db_path, args.benchmark_code)
    except RuntimeError as exc:
        raise SystemExit(f"[V3.2.1 DATA GUARD] {exc}")
    print(
        f"[DATA GUARD] PRESERVED: prices={health.stock_prices:,}, "
        f"valuation={health.valuation_snapshots:,}, features={health.ml_features:,}, "
        f"labels={health.ml_labels:,}"
    )
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
    print(f"[V3.2.1 공통위험·엄격PIT] {summary['verdict']} ({passed}/{len(summary['criteria'])} 기준 충족)")
    print(f"Champion / 내부 선택 전략: {summary['champion_strategy']} / {summary['selected_strategy']}")
    print(f"후보 / 내부 폴드 / embargo: {summary['candidate_count']}개 / {summary['nested_fold_count']}개 / {summary['embargo_days']}거래일")
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
