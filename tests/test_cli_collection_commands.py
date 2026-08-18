from types import SimpleNamespace

import pytest

from src.cli import collection_commands
from src.kis.client import KISRateLimitError


def _resolve(args):
    return list(args.codes), {}


def test_collection_dispatch_rejects_unknown_command():
    with pytest.raises(ValueError, match="지원하지 않는 수집 명령"):
        collection_commands.run_collection_command(
            object(), object(), SimpleNamespace(command="unknown"), _resolve
        )


def test_multi_collection_continues_then_stops_on_rate_limit(monkeypatch, capsys):
    calls = []

    def collect(_conn, _client, code, _days):
        calls.append(code)
        if code == "000001":
            raise RuntimeError("temporary")
        if code == "000002":
            raise KISRateLimitError("rate limited")
        return SimpleNamespace(api_skipped=False, saved=1)

    monkeypatch.setattr(collection_commands, "KISClient", lambda settings: object())
    monkeypatch.setattr(collection_commands, "collect_prices_incremental", collect)
    args = SimpleNamespace(
        command="collect-multi",
        codes=["000001", "000002", "000003"],
        days=30,
    )

    collection_commands.run_collection_command(object(), object(), args, _resolve)

    assert calls == ["000001", "000002"]
    output = capsys.readouterr().out
    assert "다음 종목 계속" in output
    assert "남은 종목의 API 호출을 중단" in output


def test_financial_series_keeps_other_reports_after_failure(monkeypatch):
    calls = []

    def collect(_conn, _client, code, year, report_code):
        calls.append((code, year, report_code))
        if report_code == "11012":
            raise RuntimeError("temporary")
        return 3

    monkeypatch.setattr(collection_commands, "DartClient", lambda key: object())
    monkeypatch.setattr(collection_commands, "collect_financials", collect)
    settings = SimpleNamespace(dart_api_key="configured")
    args = SimpleNamespace(
        command="collect-financial-series",
        codes=["005930"],
        start_year=2025,
        end_year=2025,
    )

    collection_commands.run_collection_command(object(), settings, args, _resolve)

    assert [report for _, _, report in calls] == ["11013", "11012", "11014", "11011"]
