from datetime import date, timedelta

from database.database import connect, upsert_prices
from src.collector.collectors import collect_prices_incremental


class NoApiClient:
    def daily_prices_range(self, *args, **kwargs):
        raise AssertionError("충분한 데이터인데 API가 호출됐습니다.")


class RefreshClient:
    def __init__(self):
        self.ranges = []

    def daily_prices_range(self, code, start, end):
        self.ranges.append((code, start, end))
        return []


def test_incremental_collection_skips_api_when_coverage_is_sufficient(tmp_path):
    conn = connect(tmp_path / "test.db")
    today = date.today()
    start = today - timedelta(days=365)
    rows = [
        ("005930", start.strftime("%Y%m%d"), 1, 1, 1, 1, 1, "KIS"),
        ("005930", today.strftime("%Y%m%d"), 1, 1, 1, 1, 1, "KIS"),
    ]
    upsert_prices(conn, rows)
    result = collect_prices_incremental(conn, NoApiClient(), "005930", 365)
    assert result.api_skipped is True
    assert result.saved == 0


def test_incremental_collection_does_not_request_weekend_only_leading_gap(tmp_path):
    conn = connect(tmp_path / "weekend.db")
    today = date.today()
    desired = today - timedelta(days=365)
    while desired.weekday() != 6:
        desired += timedelta(days=1)
    monday = desired + timedelta(days=1)
    days = (today - desired).days
    upsert_prices(conn, [
        ("005380", monday.strftime("%Y%m%d"), 1, 1, 1, 1, 1, "KIS"),
        ("005380", today.strftime("%Y%m%d"), 1, 1, 1, 1, 1, "KIS"),
    ])
    result = collect_prices_incremental(conn, NoApiClient(), "005380", days)
    assert result.api_skipped is True


def test_daily_refresh_rechecks_recent_seven_days(tmp_path):
    conn = connect(tmp_path / "refresh.db")
    today = date.today()
    upsert_prices(conn, [
        ("005930", (today - timedelta(days=365)).strftime("%Y%m%d"), 1, 1, 1, 1, 1, "KIS"),
        ("005930", today.strftime("%Y%m%d"), 1, 1, 1, 1, 1, "KIS"),
    ])
    client = RefreshClient()
    result = collect_prices_incremental(conn, client, "005930", 365, refresh_days=7)
    assert result.api_skipped is False
    assert client.ranges == [("005930", today - timedelta(days=7), today)]
