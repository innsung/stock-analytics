from types import SimpleNamespace

import pytest

from database.database import connect
from src.cli.portfolio_commands import run_portfolio_command


def _unused(*args, **kwargs):
    raise AssertionError("이 콜백은 호출되면 안 됩니다.")


def test_portfolio_dispatch_rejects_unknown_command(tmp_path):
    conn = connect(tmp_path / "test.db")
    with pytest.raises(ValueError, match="지원하지 않는 포트폴리오 명령"):
        run_portfolio_command(
            conn,
            object(),
            SimpleNamespace(command="unknown"),
            resolve_codes=_unused,
            save_shadow_outputs=_unused,
            print_shadow_result=_unused,
        )
    conn.close()


def test_portfolio_verify_reports_all_missing_prices(tmp_path):
    conn = connect(tmp_path / "test.db")
    args = SimpleNamespace(
        command="portfolio-verify",
        codes=["005930", "000660"],
        benchmark_code="069500",
        industry=[],
    )
    with pytest.raises(SystemExit, match="005930, 000660, 069500"):
        run_portfolio_command(
            conn,
            object(),
            args,
            resolve_codes=_unused,
            save_shadow_outputs=_unused,
            print_shadow_result=_unused,
        )
    conn.close()
