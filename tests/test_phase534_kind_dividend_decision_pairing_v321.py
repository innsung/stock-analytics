import pandas as pd

from src.ml.phase534_kind_dividend_decision_pairing_v321 import _kind_acpt_from_dart, _pair_decision


def test_pairs_latest_direct_decision_before_notice():
    notice = pd.Series({"code": "055550", "source_url": "https://kind.krx.co.kr/external/2026/04/28/x.htm"})
    decisions = pd.DataFrame([
        {"code": "055550", "known_at": "20260423", "report_nm": "현금ㆍ현물배당결정 (2026년 1분기)", "rcept_no": "20260423800321"},
        {"code": "055550", "known_at": "20260424", "report_nm": "현금ㆍ현물배당결정(자회사의 주요경영사항)", "rcept_no": "20260424800001"},
    ])
    assert _pair_decision(notice, decisions)["rcept_no"] == "20260423800321"
    assert _kind_acpt_from_dart("20260423800321") == "20260423000321"
