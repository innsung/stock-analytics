from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests


class KindFetchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    KRX_SERVICE_UNAVAILABLE = "KRX_SERVICE_UNAVAILABLE"
    HTTP_ERROR = "HTTP_ERROR"
    PARSE_FAILED = "PARSE_FAILED"


@dataclass
class KindFetchResult:
    status: KindFetchStatus
    requested_url: str
    final_url: str
    status_code: Optional[int]
    content: str
    error: Optional[str] = None
    retryable: bool = False


FAILOVER_HOSTS = {
    "upgrade-notice.krx.co.kr",
}


def is_krx_failover_url(url: str) -> bool:
    if not url:
        return False

    lowered = url.lower()

    return any(
        host in lowered
        for host in FAILOVER_HOSTS
    )


def fetch_kind_url(
    session: requests.Session,
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = 30,
) -> KindFetchResult:
    """
    KIND URL을 요청하고 KRX 점검/failover와 일반 HTTP 오류를 구분한다.

    주의:
    - KRX failover는 PARSE_FAILED가 아니다.
    - failover는 retryable=True로 반환한다.
    """

    try:
        response = session.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

    except requests.RequestException as exc:
        return KindFetchResult(
            status=KindFetchStatus.HTTP_ERROR,
            requested_url=url,
            final_url=url,
            status_code=None,
            content="",
            error=f"{type(exc).__name__}: {exc}",
            retryable=True,
        )

    final_url = response.url or url
    if (response.encoding or "").lower() == "iso-8859-1":
        detected_encoding = response.apparent_encoding
        if detected_encoding:
            response.encoding = detected_encoding

    if is_krx_failover_url(final_url):
        return KindFetchResult(
            status=KindFetchStatus.KRX_SERVICE_UNAVAILABLE,
            requested_url=url,
            final_url=final_url,
            status_code=response.status_code,
            content=response.text,
            error="KRX redirected request to upgrade/failover service",
            retryable=True,
        )

    if not response.ok:
        retryable = response.status_code >= 500 or response.status_code == 429

        return KindFetchResult(
            status=KindFetchStatus.HTTP_ERROR,
            requested_url=url,
            final_url=final_url,
            status_code=response.status_code,
            content=response.text,
            error=f"HTTP {response.status_code}",
            retryable=retryable,
        )

    return KindFetchResult(
        status=KindFetchStatus.SUCCESS,
        requested_url=url,
        final_url=final_url,
        status_code=response.status_code,
        content=response.text,
        retryable=False,
    )


KIND_BASE_URL = "https://kind.krx.co.kr"


def fetch_kind_external_document(url: str, *, timeout: int = 30) -> KindFetchResult:
    """Fetch a resolved KIND /external/ document without using the print endpoint."""
    return fetch_kind_url(
        requests.Session(),
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )


def fetch_kind_print_document(
    doc_no: str,
    *,
    acpt_no: Optional[str] = None,
    timeout: int = 30,
) -> KindFetchResult:
    """
    KIND 공시 docNo에 대한 출력용 문서를 조회한다.

    현재 KIND viewer.js가 사용하는 공식 출력 경로:
      /common/disclsviewer.do
      ?method=searchDocInfoForPrint
      &docNo=<docNo>

    acpt_no가 있으면 먼저 viewer 페이지를 열어 세션/JSESSIONID를 초기화한다.
    """

    session = requests.Session()

    user_agent = "Mozilla/5.0"

    viewer_url = f"{KIND_BASE_URL}/common/disclsviewer.do"

    referer = KIND_BASE_URL

    if acpt_no:
        initial_result = fetch_kind_url(
            session,
            viewer_url,
            params={
                "method": "search",
                "acptno": acpt_no,
            },
            headers={
                "User-Agent": user_agent,
            },
            timeout=timeout,
        )

        if initial_result.status != KindFetchStatus.SUCCESS:
            return initial_result

        referer = initial_result.final_url

    return fetch_kind_url(
        session,
        viewer_url,
        params={
            "method": "searchDocInfoForPrint",
            "docNo": doc_no,
        },
        headers={
            "User-Agent": user_agent,
            "Referer": referer,
        },
        timeout=timeout,
    )
