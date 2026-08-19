from types import SimpleNamespace

import pytest

from database.database import connect
from src.cli.event_commands import run_event_command


def _unused(*args, **kwargs):
    raise AssertionError("이 콜백은 호출되면 안 됩니다.")


def test_event_dispatch_rejects_unknown_command(tmp_path):
    conn = connect(tmp_path / "test.db")
    with pytest.raises(ValueError, match="지원하지 않는 이벤트 명령"):
        run_event_command(
            conn,
            object(),
            SimpleNamespace(command="unknown"),
            load_universe=_unused,
        )
    conn.close()


def test_event_reconciliation_reports_missing_sources(tmp_path):
    conn = connect(tmp_path / "test.db")
    args = SimpleNamespace(
        command="build-event-reconciliation-v321",
        dividend_facts_csv=str(tmp_path / "missing-dividends.csv"),
        action_disclosures_csv=str(tmp_path / "missing-actions.csv"),
        output_csv=str(tmp_path / "queue.csv"),
    )

    with pytest.raises(SystemExit, match="Phase 5.3"):
        run_event_command(conn, object(), args, load_universe=_unused)
    conn.close()
