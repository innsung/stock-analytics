from pathlib import Path
import pandas as pd
import pytest

from src.ml.historical_acquisition_v321 import (
    PykrxProvider,
    acquire_historical_data_v321,
)


class FakeProvider:
    def fundamentals(self, start, end, code, frequency):
        return pd.DataFrame({"BPS":[10000,11000],"PER":[10.0,11.0],"PBR":[1.0,1.1],"EPS":[1000,1000],"DIV":[2.0,1.8]}, index=pd.to_datetime(["2026-06-30","2026-07-09"]))
    def market_cap(self, start, end, code, frequency):
        return pd.DataFrame({"시가총액":[100_000_000_000,110_000_000_000]}, index=pd.to_datetime(["2026-06-30","2026-07-09"]))
    def ohlcv(self, start, end, code, frequency):
        return pd.DataFrame({"종가":[10000,11000]}, index=pd.to_datetime(["2026-06-30","2026-07-09"]))
    def index_constituents(self, index_code, date):
        return ["005930", "000660"]


def test_provider_preflight_does_not_expose_third_party_login_output(capsys):
    provider = object.__new__(PykrxProvider)
    provider.request_timeout = 1
    provider.installed_version = "test"

    class NoisyStock:
        @staticmethod
        def get_market_fundamental(*args, **kwargs):
            print("secret-login-id")
            return pd.DataFrame({"PER": [10.0]}, index=["20260709"])

    provider.stock = NoisyStock()
    assert provider.preflight("005930", "20260709")["ok"] is True
    assert "secret-login-id" not in capsys.readouterr().out


def test_phase4_acquires_strict_valuation_and_observations(tmp_path):
    universe = tmp_path / "universe.csv"
    universe.write_text("code,enabled\n005930,true\n", encoding="utf-8")
    out = tmp_path / "raw"
    result = acquire_historical_data_v321(
        str(universe), "20260601", "20260709", str(out), index_code="1028",
        provider=FakeProvider(), sleep_seconds=0)
    assert result["valuation_strict_verified"] is True
    assert result["valuation_rows"] == 2
    assert result["universe_observation_rows"] == 4
    val = pd.read_csv(out / "valuation_snapshots.csv", dtype={"code": str})
    assert set(val["source"]) == {"KRX_PYKRX_EOD"}
    assert set(val["known_at"].astype(str)) == {"20260630", "20260709"}
    assert not (out / "total_return_history.csv").exists()
    assert "not equivalent" in result["blockers"]["total_return"]
    assert (out / "provider_status.json").exists()
    provider_status = __import__("json").loads((out / "provider_status.json").read_text(encoding="utf-8"))
    assert provider_status["ok"] is True
    assert provider_status["preflight"] == "CUSTOM_PROVIDER_SKIPPED"


def test_phase4_rejects_post_cutoff(tmp_path):
    universe = tmp_path / "universe.csv"
    universe.write_text("code\n005930\n", encoding="utf-8")
    with pytest.raises(ValueError, match="연구 경계"):
        acquire_historical_data_v321(str(universe), "20260701", "20260710", str(tmp_path / "out"), provider=FakeProvider(), sleep_seconds=0)


def test_phase4_missing_universe_is_friendly(tmp_path):
    with pytest.raises(FileNotFoundError, match="유니버스 파일"):
        acquire_historical_data_v321(str(tmp_path / "missing.csv"), "20260101", "20260709", str(tmp_path / "out"), provider=FakeProvider(), sleep_seconds=0)
