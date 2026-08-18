from src.ml.phase577_broadened_kind_notice_resolution_v321 import _membership_rank


def test_exact_company_field_beats_aggregate_alias_membership():
    assert _membership_rank("1. 회사명 셀트리온 2. 주권종류와 가격", ["셀트리온"])[0] == 1
    assert _membership_rank("결산배당락 종목: 현대차, 다른회사", ["현대자동차","현대차"])[0] == 2
    assert _membership_rank("회사명 현대약품", ["현대자동차","현대차"])[0] == 99
