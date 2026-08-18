from argparse import Namespace

from src.main import load_universe_csv, resolve_codes_and_industries


def test_universe_csv_keeps_leading_zero_and_enabled_rows(tmp_path):
    path = tmp_path / "universe.csv"
    path.write_text("code,industry,enabled\n005930,반도체,true\n000660,반도체,false\n", encoding="utf-8")
    codes, industries = load_universe_csv(str(path))
    assert codes == ["005930"]
    assert industries == {"005930": "반도체"}
    args = Namespace(universe_csv=str(path), codes=["035420"], industry=["035420=인터넷"])
    resolved, mapping = resolve_codes_and_industries(args)
    assert resolved == ["005930", "035420"]
    assert mapping["035420"] == "인터넷"
