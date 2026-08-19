from types import SimpleNamespace

import pytest

from database.database import connect
from src.cli.runtime_commands import run_runtime_command


def _unused(*args, **kwargs):
    raise AssertionError("이 콜백은 호출되면 안 됩니다.")


def test_runtime_dispatch_rejects_unknown_command(tmp_path):
    conn = connect(tmp_path / "test.db")
    with pytest.raises(ValueError, match="지원하지 않는 운영 명령"):
        run_runtime_command(
            conn,
            object(),
            SimpleNamespace(command="unknown"),
            resolve_codes=_unused,
            print_shadow_report=_unused,
            execute_daily_shadow=_unused,
        )
    conn.close()


def test_daily_status_handles_empty_log_table(tmp_path, capsys):
    conn = connect(tmp_path / "test.db")
    args = SimpleNamespace(command="daily-status", portfolio_id=None, limit=10)
    run_runtime_command(
        conn,
        object(),
        args,
        resolve_codes=_unused,
        print_shadow_report=_unused,
        execute_daily_shadow=_unused,
    )
    assert "실행 기록이 없습니다" in capsys.readouterr().out
    conn.close()


def test_daily_shadow_delegates_to_guarded_runner(tmp_path):
    conn = connect(tmp_path / "test.db")
    received = []
    args = SimpleNamespace(command="daily-shadow")

    run_runtime_command(
        conn,
        "settings",
        args,
        resolve_codes=_unused,
        print_shadow_report=_unused,
        execute_daily_shadow=lambda *values: received.append(values),
    )

    assert received == [(conn, "settings", args)]
    conn.close()
