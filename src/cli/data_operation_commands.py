from __future__ import annotations

import sqlite3

from src.ml.data_integrity_v321 import (
    build_data_foundation_v321,
    import_valuation_snapshots,
)
from src.ml.historical_acquisition_v321 import (
    acquire_historical_data_v321,
    check_krx_provider_v321,
)
from src.ml.persistent_data_v321 import (
    backup_database_v321,
    inspect_persistent_data_v321,
    write_health_snapshot_v321,
)


DATA_OPERATION_COMMANDS = frozenset({
    "import-valuation-snapshots-v321",
    "build-data-foundation-v321",
    "krx-provider-check-v321",
    "acquire-historical-data-v321",
    "db-health-v321",
    "backup-db-v321",
})


def run_data_operation_command(
    conn: sqlite3.Connection,
    settings,
    args,
) -> None:
    """Run guarded V3.2.1 data acquisition, health, and backup commands."""
    if args.command not in DATA_OPERATION_COMMANDS:
        raise ValueError(f"지원하지 않는 데이터 운영 명령입니다: {args.command}")

    if args.command == "import-valuation-snapshots-v321":
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
