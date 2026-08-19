from types import SimpleNamespace

import pytest

from database.database import connect
from src.cli.dividend_commands import run_dividend_command


def test_dividend_dispatch_rejects_unknown_command(tmp_path):
    conn = connect(tmp_path / "test.db")
    with pytest.raises(ValueError, match="지원하지 않는 배당 검증 명령"):
        run_dividend_command(
            conn, object(), SimpleNamespace(command="unknown")
        )
    conn.close()


def test_cash_candidate_builder_reports_missing_inputs(tmp_path):
    conn = connect(tmp_path / "test.db")
    args = SimpleNamespace(
        command="build-stock-cash-amount-candidates-v321",
        dividend_facts_csv=str(tmp_path / "missing-dividends.csv"),
        verification_csv=str(tmp_path / "missing-verification.csv"),
        output_csv=str(tmp_path / "candidates.csv"),
        audit_csv=str(tmp_path / "audit.csv"),
        etf_code=[],
    )

    with pytest.raises(SystemExit, match="Phase 5.8"):
        run_dividend_command(conn, object(), args)
    conn.close()
