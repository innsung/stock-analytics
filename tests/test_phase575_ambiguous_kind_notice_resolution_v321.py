from src.ml.phase575_ambiguous_kind_notice_resolution_v321 import COMPANY_FIELD


def test_company_field_requires_exact_company_not_prefix():
    group = COMPANY_FIELD.search("1. 회사명 아모레퍼시픽그룹 2. 주권종류와 가격")
    company = COMPANY_FIELD.search("1. 회사명 아모레퍼시픽 2. 주권종류와 가격")
    assert group.group(1) != "아모레퍼시픽"
    assert company.group(1) == "아모레퍼시픽"
