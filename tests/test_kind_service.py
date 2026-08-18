from src.kind_service import (
    KindFetchStatus,
    fetch_kind_url,
    is_krx_failover_url,
)


def test_is_krx_failover_url_true():
    url = (
        "https://upgrade-notice.krx.co.kr/failover/index.html"
        "?method=searchDocInfoForPrint&docNo=20260527001263"
    )

    assert is_krx_failover_url(url) is True


def test_is_krx_failover_url_false():
    url = (
        "https://kind.krx.co.kr/common/disclsviewer.do"
        "?method=search&acptno=20260527000541"
    )

    assert is_krx_failover_url(url) is False


def test_status_values_are_stable():
    assert KindFetchStatus.SUCCESS.value == "SUCCESS"
    assert (
        KindFetchStatus.KRX_SERVICE_UNAVAILABLE.value
        == "KRX_SERVICE_UNAVAILABLE"
    )
    assert KindFetchStatus.HTTP_ERROR.value == "HTTP_ERROR"
    assert KindFetchStatus.PARSE_FAILED.value == "PARSE_FAILED"


def test_fetch_kind_url_corrects_default_iso_8859_1_decoding():
    class Response:
        url = "https://kind.krx.co.kr/external/document.htm"
        status_code = 200
        ok = True
        encoding = "ISO-8859-1"
        apparent_encoding = "utf-8"
        content = "배당".encode("utf-8")

        @property
        def text(self):
            return self.content.decode(self.encoding)

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    result = fetch_kind_url(Session(), "https://kind.krx.co.kr/external/document.htm")
    assert result.status == KindFetchStatus.SUCCESS
    assert result.content == "배당"
