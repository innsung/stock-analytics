from src.ml.phase533_kind_batch_market_search_v321 import _months


def test_month_windows_are_bounded():
    assert list(_months("20260115", "20260310")) == [
        ("2026-01-01", "2026-01-31"),
        ("2026-02-01", "2026-02-28"),
        ("2026-03-01", "2026-03-10"),
    ]
