from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import json
import sqlite3


CRITICAL_TABLES = (
    "stock_prices",
    "valuation_snapshots",
    "ml_features",
    "ml_labels",
)


@dataclass(frozen=True)
class DataHealth:
    db_path: str
    db_bytes: int
    stock_prices: int
    price_codes: int
    benchmark_rows: int
    valuation_snapshots: int
    valuation_codes: int
    ml_features: int
    feature_codes: int
    ml_labels: int
    label_codes: int
    healthy_for_v321: bool


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _count(conn: sqlite3.Connection, table: str, where: str = "", params=()) -> int:
    if not _table_exists(conn, table):
        return 0
    sql = f"SELECT COUNT(*) FROM {table}" + (f" WHERE {where}" if where else "")
    return int(conn.execute(sql, params).fetchone()[0])


def _distinct(conn: sqlite3.Connection, table: str, column: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(DISTINCT {column}) FROM {table}").fetchone()[0])


def inspect_persistent_data_v321(conn: sqlite3.Connection, db_path: Path,
                                 benchmark_code: str = "069500") -> DataHealth:
    stock_prices = _count(conn, "stock_prices")
    price_codes = _distinct(conn, "stock_prices", "code")
    benchmark_rows = _count(conn, "stock_prices", "code=?", (benchmark_code,))
    valuations = _count(conn, "valuation_snapshots")
    valuation_codes = _distinct(conn, "valuation_snapshots", "code")
    features = _count(conn, "ml_features")
    feature_codes = _distinct(conn, "ml_features", "code")
    labels = _count(conn, "ml_labels")
    label_codes = _distinct(conn, "ml_labels", "code")
    # The guard deliberately checks existence/non-emptiness rather than historical
    # exact row counts so legitimate incremental updates do not trip it.
    healthy = bool(
        stock_prices > 0 and price_codes >= 2 and benchmark_rows > 0
        and valuations > 0 and features > 0 and labels > 0
    )
    size = db_path.stat().st_size if db_path.exists() else 0
    return DataHealth(
        db_path=str(db_path), db_bytes=size,
        stock_prices=stock_prices, price_codes=price_codes,
        benchmark_rows=benchmark_rows,
        valuation_snapshots=valuations, valuation_codes=valuation_codes,
        ml_features=features, feature_codes=feature_codes,
        ml_labels=labels, label_codes=label_codes,
        healthy_for_v321=healthy,
    )


def assert_persistent_data_v321(conn: sqlite3.Connection, db_path: Path,
                                benchmark_code: str = "069500") -> DataHealth:
    health = inspect_persistent_data_v321(conn, db_path, benchmark_code)
    if not health.healthy_for_v321:
        raise RuntimeError(
            "V3.2.1 persistent data guard failed: "
            f"stock_prices={health.stock_prices}, price_codes={health.price_codes}, "
            f"benchmark_rows={health.benchmark_rows}, valuation_snapshots={health.valuation_snapshots}, "
            f"ml_features={health.ml_features}, ml_labels={health.ml_labels}. "
            "데이터를 자동 재수집하거나 초기화하지 않습니다. DB 경로/백업을 확인하세요."
        )
    return health


def write_health_snapshot_v321(health: DataHealth, path: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(health) | {"checked_at": datetime.now().astimezone().isoformat()}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)


def backup_database_v321(conn: sqlite3.Connection, db_path: Path, output_dir: str,
                         label: str = "manual") -> dict:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:40] or "backup"
    target = target_dir / f"stock_analytics_{stamp}_{safe_label}.db"
    # SQLite online backup keeps a transactionally consistent copy even under WAL.
    with sqlite3.connect(target) as dst:
        conn.backup(dst)
    source_health = inspect_persistent_data_v321(conn, db_path)
    with sqlite3.connect(target) as verify:
        backup_health = inspect_persistent_data_v321(verify, target)
    keys = ("stock_prices", "price_codes", "benchmark_rows", "valuation_snapshots",
            "valuation_codes", "ml_features", "feature_codes", "ml_labels", "label_codes")
    verified = all(getattr(source_health, k) == getattr(backup_health, k) for k in keys)
    if not verified:
        target.unlink(missing_ok=True)
        raise RuntimeError("DB 백업 검증 실패: 원본과 백업의 핵심 테이블 행 수가 다릅니다.")
    manifest = target.with_suffix(".json")
    manifest.write_text(json.dumps({
        "source": asdict(source_health),
        "backup": asdict(backup_health),
        "verified": True,
        "created_at": datetime.now().astimezone().isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"backup_path": str(target), "manifest_path": str(manifest), "verified": True}
