from datetime import date, timedelta

from config.settings import Settings
import pytest

from src.kis.client import KISClient, KISRateLimitError


class Response:
    def __init__(self, rows):
        self.rows = rows

    def raise_for_status(self):
        pass

    def json(self):
        return {"rt_cd": "0", "output2": self.rows}


class Session:
    def __init__(self):
        self.calls = 0
        self.post_calls = 0

    def post(self, *args, **kwargs):
        self.post_calls += 1
        return type("TokenResponse", (), {"raise_for_status": lambda self: None, "json": lambda self: {"access_token": "token"}})()

    def get(self, *args, **kwargs):
        self.calls += 1
        end = date.fromisoformat(f"{kwargs['params']['fid_input_date_2'][:4]}-{kwargs['params']['fid_input_date_2'][4:6]}-{kwargs['params']['fid_input_date_2'][6:]}")
        if self.calls > 3:
            return Response([])
        rows = []
        for offset in range(100):
            day = (end - timedelta(days=offset)).strftime("%Y%m%d")
            rows.append({"stck_bsop_date": day})
        return Response(rows)


def test_daily_prices_fetches_more_than_one_page(tmp_path):
    settings = Settings("virtual", "key", "secret", "dart", tmp_path / "db.sqlite", "INFO")
    session = Session()
    rows = KISClient(settings, session).daily_prices("005930", days=250)
    assert len(rows) > 100
    assert session.calls >= 2
    assert len({row["stck_bsop_date"] for row in rows}) == len(rows)
    second_session = Session()
    assert KISClient(settings, second_session).access_token() == "token"
    assert second_session.post_calls == 0


def test_token_rate_limit_has_clear_message(tmp_path):
    settings = Settings("virtual", "key2", "secret", "dart", tmp_path / "other" / "db.sqlite", "INFO")
    class LimitedSession:
        def post(self, *args, **kwargs):
            return type("Limited", (), {"status_code": 403, "raise_for_status": lambda self: None})()
    with pytest.raises(KISRateLimitError, match="1분 이상"):
        KISClient(settings, LimitedSession()).access_token()
