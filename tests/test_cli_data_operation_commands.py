from types import SimpleNamespace

import pytest

from database.database import connect
from src.cli import data_operation_commands


def test_data_operation_dispatch_rejects_unknown_command(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    with pytest.raises(ValueError, match="지원하지 않는 데이터 운영 명령"):
        data_operation_commands.run_data_operation_command(
            conn,
            SimpleNamespace(db_path=db_path),
            SimpleNamespace(command="unknown"),
        )
    conn.close()


def test_db_health_reports_not_ready_without_mutating_data(tmp_path, capsys):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    args = SimpleNamespace(
        command="db-health-v321",
        benchmark_code="069500",
        output_json=None,
    )

    data_operation_commands.run_data_operation_command(
        conn, SimpleNamespace(db_path=db_path), args
    )

    assert "NOT_READY" in capsys.readouterr().out
    assert conn.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0] == 0
    conn.close()


def test_krx_guard_converts_boundary_error_to_clear_exit(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    monkeypatch.setattr(
        data_operation_commands,
        "check_krx_provider_v321",
        lambda code, end: (_ for _ in ()).throw(ValueError("연구 경계 초과")),
    )
    args = SimpleNamespace(
        command="krx-provider-check-v321", code="005930", end="20990101"
    )

    with pytest.raises(SystemExit, match="KRX Provider Check.*연구 경계 초과"):
        data_operation_commands.run_data_operation_command(
            conn, SimpleNamespace(db_path=db_path), args
        )
    conn.close()
