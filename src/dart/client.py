import io
import re
import zipfile
from typing import Any

import requests


class DartClient:
    base_url = "https://opendart.fss.or.kr/api"

    def __init__(self, api_key: str, session: requests.Session | None = None):
        if not api_key:
            raise ValueError("DART_API_KEY를 .env에 입력하세요.")
        self.api_key = api_key
        self.session = session or requests.Session()
        self._corp_map: dict[str, str] | None = None

    def corp_code_map(self) -> dict[str, str]:
        if self._corp_map is not None:
            return self._corp_map
        response = self.session.get(f"{self.base_url}/corpCode.xml", params={"crtfc_key": self.api_key}, timeout=30)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            xml = archive.read("CORPCODE.xml").decode("utf-8")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
        self._corp_map = {item.findtext("stock_code"): item.findtext("corp_code") for item in root.findall("list") if item.findtext("stock_code")}
        return self._corp_map

    def stock_name_map(self) -> dict[str, str]:
        """Return current OpenDART stock-code to corporation-name mappings."""
        response = self.session.get(f"{self.base_url}/corpCode.xml", params={"crtfc_key": self.api_key}, timeout=30)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            xml = archive.read("CORPCODE.xml").decode("utf-8")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
        return {item.findtext("stock_code"): item.findtext("corp_name")
                for item in root.findall("list") if item.findtext("stock_code")}

    def financials(self, corp_code: str, year: int, report_code: str = "11011",
                   fs_div: str = "CFS") -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.base_url}/fnlttSinglAcntAll.json",
            params={"crtfc_key": self.api_key, "corp_code": corp_code, "bsns_year": year,
                    "reprt_code": report_code, "fs_div": fs_div}, timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        # 013은 해당 조건의 공시 데이터가 없다는 공식 응답이다. 호출자가
        # CFS -> OFS 보조 조회를 할 수 있도록 빈 목록으로 돌려준다.
        if payload.get("status") == "013":
            return []
        if payload.get("status") != "000":
            raise RuntimeError(f"DART 오류 {payload.get('status')}: {payload.get('message')}")
        return payload.get("list", [])

    def disclosure_date(self, corp_code: str, year: int, report_code: str) -> str | None:
        names = {"11011": "사업보고서", "11012": "반기보고서", "11013": "분기보고서", "11014": "분기보고서"}
        response = self.session.get(
            f"{self.base_url}/list.json",
            params={"crtfc_key": self.api_key, "corp_code": corp_code,
                    "bgn_de": f"{year}0101", "end_de": f"{year + 1}1231", "pblntf_ty": "A", "page_count": 100},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in {"000", None}:
            return None
        candidates = [item for item in payload.get("list", [])
                      if names.get(report_code, "") in item.get("report_nm", "")]
        if report_code in {"11013", "11014"}:
            quarter = "1분기" if report_code == "11013" else "3분기"
            narrowed = [item for item in candidates if quarter in item.get("report_nm", "")]
            candidates = narrowed or candidates
        return min((item.get("rcept_dt") for item in candidates if item.get("rcept_dt")), default=None)

    def dividend_matters(self, corp_code: str, year: int, report_code: str = "11011") -> list[dict[str, Any]]:
        """OpenDART periodic-report dividend facts (alotMatter).

        These are disclosure facts, not ex-date/payment-date events. Callers must
        not promote them directly to canonical Total Return cash distributions.
        """
        response = self.session.get(
            f"{self.base_url}/alotMatter.json",
            params={"crtfc_key": self.api_key, "corp_code": corp_code,
                    "bsns_year": int(year), "reprt_code": report_code},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "013":
            return []
        if payload.get("status") != "000":
            raise RuntimeError(f"DART 오류 {payload.get('status')}: {payload.get('message')}")
        return payload.get("list", [])

    def disclosure_list(self, corp_code: str, begin: str, end: str,
                        page_count: int = 100) -> list[dict[str, Any]]:
        """Return disclosure metadata for raw corporate-action decision discovery."""
        response = self.session.get(
            f"{self.base_url}/list.json",
            params={"crtfc_key": self.api_key, "corp_code": corp_code,
                    "bgn_de": begin, "end_de": end, "page_count": page_count},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "013":
            return []
        if payload.get("status") not in {"000", None}:
            raise RuntimeError(f"DART 오류 {payload.get('status')}: {payload.get('message')}")
        return payload.get("list", [])

    def major_event(self, endpoint: str, corp_code: str, begin: str, end: str) -> list[dict[str, Any]]:
        """Fetch one OpenDART major-event endpoint over a receipt-date range."""
        allowed = {
            "fricDecsn", "cmpMgDecsn", "cmpDvDecsn", "cmpDvmgDecsn", "stkExtrDecsn",
        }
        if endpoint not in allowed:
            raise ValueError(f"허용되지 않은 OpenDART major-event endpoint: {endpoint}")
        response = self.session.get(
            f"{self.base_url}/{endpoint}.json",
            params={"crtfc_key": self.api_key, "corp_code": corp_code,
                    "bgn_de": begin, "end_de": end},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "013":
            return []
        if payload.get("status") != "000":
            raise RuntimeError(f"DART 오류 {payload.get('status')}: {payload.get('message')}")
        return payload.get("list", [])

    def document_texts(self, rcept_no: str) -> list[dict[str, str]]:
        """Download an OpenDART filing document archive and return decoded text parts.

        OpenDART document.xml returns a ZIP containing filing XML/HTML fragments.
        This method preserves part names and decodes conservatively for downstream
        evidence extraction. It does not interpret dates or event semantics.
        """
        response = self.session.get(
            f"{self.base_url}/document.xml",
            params={"crtfc_key": self.api_key, "rcept_no": str(rcept_no)},
            timeout=30,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        raw = response.content
        # OpenDART error responses may be XML rather than ZIP.
        if not raw.startswith(b"PK"):
            sample = raw[:1000].decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"DART document.xml 응답이 ZIP이 아닙니다. content-type={content_type}, sample={sample[:200]}"
            )
        parts: list[dict[str, str]] = []
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                data = archive.read(name)
                text = ""
                header = data[:2048].decode("ascii", errors="ignore")
                declared = re.search(
                    r"(?:encoding\s*=\s*['\"]|charset\s*=\s*)([A-Za-z0-9._-]+)",
                    header,
                    flags=re.IGNORECASE,
                )
                encodings = ([declared.group(1)] if declared else []) + ["utf-8", "cp949", "euc-kr"]
                for enc in dict.fromkeys(encodings):
                    try:
                        text = data.decode(enc)
                        break
                    except (LookupError, UnicodeDecodeError):
                        continue
                if not text:
                    text = data.decode("utf-8", errors="ignore")
                parts.append({"name": name, "text": text})
        return parts
