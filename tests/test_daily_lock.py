import pytest

from src.main import daily_run_lock


def test_daily_run_lock_blocks_same_portfolio(tmp_path):
    db_path = tmp_path / "data.db"
    with daily_run_lock(db_path, "shadow_24_filtered"):
        with pytest.raises(RuntimeError, match="이미 실행 중"):
            with daily_run_lock(db_path, "shadow_24_filtered"):
                pass
    with daily_run_lock(db_path, "shadow_24_filtered"):
        pass
