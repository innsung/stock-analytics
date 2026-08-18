from types import SimpleNamespace

import pytest

from database.database import connect
from src.cli.core_commands import run_core_command


def test_core_command_dispatch_rejects_unknown_command(tmp_path):
    conn = connect(tmp_path / "test.db")
    with pytest.raises(ValueError, match="지원하지 않는 핵심 명령"):
        run_core_command(conn, SimpleNamespace(command="unknown"))
    conn.close()


def test_core_command_reports_missing_prices(tmp_path):
    conn = connect(tmp_path / "test.db")
    args = SimpleNamespace(command="analyze", code="005930")
    with pytest.raises(SystemExit, match="collect-price"):
        run_core_command(conn, args)
    conn.close()
