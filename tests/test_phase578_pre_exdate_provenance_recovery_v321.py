import pandas as pd

from src.ml.phase578_pre_exdate_provenance_recovery_v321 import COMPANY_FIELD


def test_company_field_extracts_exact_market_issuer():
    assert COMPANY_FIELD.search("1. 회사명 현대모비스 2. 주권종류와 가격").group(1) == "현대모비스"
