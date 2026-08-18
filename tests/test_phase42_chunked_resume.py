from pathlib import Path
import pandas as pd
import pytest

from src.ml.historical_acquisition_v321 import acquire_valuation_history, _year_chunks


class FlakyAnnualProvider:
    def __init__(self):
        self.calls = {}

    def _frame(self, start, kind):
        year = int(start[:4])
        date = f"{year}-12-30"
        if kind == "f":
            return pd.DataFrame({"BPS":[10000], "PER":[10.0], "PBR":[1.0], "EPS":[1000], "DIV":[2.0]}, index=pd.to_datetime([date]))
        if kind == "c":
            return pd.DataFrame({"시가총액":[100_000_000_000]}, index=pd.to_datetime([date]))
        return pd.DataFrame({"종가":[10000]}, index=pd.to_datetime([date]))

    def fundamentals(self, start, end, code, frequency):
        key=(code,start,"f")
        self.calls[key]=self.calls.get(key,0)+1
        if start.startswith("2021") and self.calls[key] == 1:
            raise TimeoutError("simulated timeout")
        return self._frame(start,"f")

    def market_cap(self, start, end, code, frequency):
        key=(code,start,"c"); self.calls[key]=self.calls.get(key,0)+1
        return self._frame(start,"c")

    def ohlcv(self, start, end, code, frequency):
        key=(code,start,"p"); self.calls[key]=self.calls.get(key,0)+1
        return self._frame(start,"p")

    def index_constituents(self, index_code, date):
        return []


class MustNotBeCalledProvider:
    def fundamentals(self, *args, **kwargs): raise AssertionError("resume should skip completed chunks")
    def market_cap(self, *args, **kwargs): raise AssertionError("resume should skip completed chunks")
    def ohlcv(self, *args, **kwargs): raise AssertionError("resume should skip completed chunks")
    def index_constituents(self, *args, **kwargs): return []


def test_phase42_year_chunks_are_annual_and_bounded():
    assert _year_chunks("20201115", "20220203") == [
        ("20201115", "20201231"),
        ("20210101", "20211231"),
        ("20220101", "20220203"),
    ]


def test_phase42_retry_checkpoint_and_resume(tmp_path):
    cp = tmp_path / "checkpoints"
    messages=[]
    provider=FlakyAnnualProvider()
    frame, audit = acquire_valuation_history(
        provider, ["005930"], "20200101", "20221231", "m", sleep_seconds=0,
        checkpoint_dir=cp, max_retries=3, retry_backoff_seconds=0, resume=True,
        progress=messages.append,
    )
    assert len(frame) == 3
    assert set(frame["snapshot_date"].astype(str)) == {"20201230", "20211230", "20221230"}
    a2021=audit[audit["chunk_start"] == "20210101"].iloc[0]
    assert a2021["status"] == "OK"
    assert int(a2021["attempts"]) == 2
    assert len(list(cp.glob("*.done.json"))) == 3
    assert any("재시도" in m for m in messages)

    messages2=[]
    frame2, audit2 = acquire_valuation_history(
        MustNotBeCalledProvider(), ["005930"], "20200101", "20221231", "m", sleep_seconds=0,
        checkpoint_dir=cp, max_retries=3, retry_backoff_seconds=0, resume=True,
        progress=messages2.append,
    )
    assert len(frame2) == 3
    assert set(audit2["status"]) == {"RESUMED"}
    assert sum("RESUME/SKIP" in m for m in messages2) == 3


def test_phase42_invalid_retry_count_is_rejected(tmp_path):
    from src.ml.historical_acquisition_v321 import acquire_historical_data_v321
    universe=tmp_path/"u.csv"
    universe.write_text("code\n005930\n", encoding="utf-8")
    with pytest.raises(ValueError, match="max-retries"):
        acquire_historical_data_v321(str(universe), "20260101", "20260709", str(tmp_path/"out"), provider=FlakyAnnualProvider(), max_retries=0, progress=None)

def test_phase42_requests_timeout_is_injected(monkeypatch):
    import requests
    from src.ml.historical_acquisition_v321 import _requests_timeout
    seen = {}
    def fake_request(self, method, url, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return "ok"
    monkeypatch.setattr(requests.sessions.Session, "request", fake_request)
    with _requests_timeout(12.5):
        result = requests.Session().request("GET", "https://example.invalid")
    assert result == "ok"
    assert seen["timeout"] == 12.5


class AlwaysFailProvider(FlakyAnnualProvider):
    def fundamentals(self, start, end, code, frequency):
        raise TimeoutError("always timeout")


def test_phase42_failed_chunk_is_not_checkpointed(tmp_path):
    cp = tmp_path / "checkpoints"
    frame, audit = acquire_valuation_history(
        AlwaysFailProvider(), ["005930"], "20260101", "20260709", "m", sleep_seconds=0,
        checkpoint_dir=cp, max_retries=2, retry_backoff_seconds=0, resume=True, progress=None)
    assert frame.empty
    assert audit.iloc[0]["status"] == "ERROR"
    assert int(audit.iloc[0]["attempts"]) == 2
    assert not list(cp.glob("*.done.json"))
