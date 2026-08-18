from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any
from zoneinfo import ZoneInfo

import requests

from config.settings import Settings


class KISRateLimitError(RuntimeError):
    pass


class KISClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        if not settings.kis_app_key or not settings.kis_app_secret:
            raise ValueError("KIS_APP_KEY와 KIS_APP_SECRET을 .env에 입력하세요.")
        self.settings = settings
        self.session = session or requests.Session()
        self._token: str | None = None
        self.cache_path = settings.db_path.parent / ".kis_token_cache.json"

    def _fingerprint(self) -> str:
        raw = f"{self.settings.kis_base_url}:{self.settings.kis_app_key}".encode()
        return hashlib.sha256(raw).hexdigest()

    def _load_cached_token(self) -> str | None:
        try:
            cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
            expires = datetime.fromisoformat(cached["expires_at"])
            if cached.get("fingerprint") == self._fingerprint() and expires > datetime.now(timezone.utc) + timedelta(minutes=2):
                return cached["access_token"]
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return None
        return None

    def _save_token(self, token: str, payload: dict[str, Any]) -> None:
        expires = datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 23 * 3600)))
        raw_expiry = payload.get("access_token_token_expired")
        if raw_expiry:
            try:
                expires = datetime.strptime(raw_expiry, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=ZoneInfo("Asia/Seoul")
                ).astimezone(timezone.utc)
            except ValueError:
                pass
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps({"fingerprint": self._fingerprint(), "access_token": token,
                                               "expires_at": expires.isoformat()}), encoding="utf-8")
        try:
            self.cache_path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _check_http(response, context: str) -> None:
        status = getattr(response, "status_code", 200)
        if status in {403, 429}:
            raise KISRateLimitError(
                f"KIS {context} 제한({status})입니다. 토큰은 캐시되며 자동 재시도하지 않습니다. "
                "토큰 발급 직후라면 1분 이상 기다리거나 --skip-collect로 저장 데이터를 사용하세요."
            )
        response.raise_for_status()

    def _get(self, url: str, *, headers: dict[str, str], params: dict[str, str],
             context: str, attempts: int = 3):
        """일시적인 KIS 5xx만 제한적으로 재시도한다.

        403/429는 즉시 중단하고, 무한 재시도는 하지 않는다.
        """
        response = None
        for attempt in range(attempts):
            response = self.session.get(url, headers=headers, params=params, timeout=15)
            if getattr(response, "status_code", 200) < 500:
                self._check_http(response, context)
                return response
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
        self._check_http(response, context)
        return response

    def access_token(self) -> str:
        if self._token:
            return self._token
        self._token = self._load_cached_token()
        if self._token:
            return self._token
        response = self.session.post(
            f"{self.settings.kis_base_url}/oauth2/tokenP",
            json={"grant_type": "client_credentials", "appkey": self.settings.kis_app_key,
                  "appsecret": self.settings.kis_app_secret}, timeout=15,
        )
        self._check_http(response, "접근토큰 발급")
        payload = response.json()
        self._token = payload["access_token"]
        self._save_token(self._token, payload)
        return self._token

    def _headers(self, tr_id: str) -> dict[str, str]:
        return {"authorization": f"Bearer {self.access_token()}", "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret, "tr_id": tr_id}

    def daily_prices(self, code: str, days: int = 365) -> list[dict[str, Any]]:
        if days < 1:
            raise ValueError("days는 1 이상이어야 합니다.")
        today = date.today()
        return self.daily_prices_range(code, today - timedelta(days=days), today)

    def daily_prices_range(self, code: str, start: date, end: date) -> list[dict[str, Any]]:
        if start > end:
            return []
        cursor_end = end
        collected: dict[str, dict[str, Any]] = {}
        while cursor_end >= start:
            params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code,
                      "fid_input_date_1": start.strftime("%Y%m%d"),
                      "fid_input_date_2": cursor_end.strftime("%Y%m%d"),
                      "fid_period_div_code": "D", "fid_org_adj_prc": "0"}
            try:
                response = self._get(
                f"{self.settings.kis_base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
                headers=self._headers("FHKST03010100"),
                params=params, context="시세 조회")
            except requests.HTTPError as exc:
                # VTS는 휴장일 단 하루 조회에 간헐적으로 500을 반환한다.
                if start == cursor_end and exc.response is not None and exc.response.status_code >= 500:
                    return [collected[key] for key in sorted(collected)]
                raise
            payload = response.json()
            if payload.get("rt_cd") not in (None, "0"):
                raise RuntimeError(f"KIS 오류: {payload.get('msg1', payload)}")
            page = payload.get("output2", [])
            if not page:
                break
            valid_dates = []
            for item in page:
                raw_date = item.get("stck_bsop_date", "")
                if raw_date and start.strftime("%Y%m%d") <= raw_date <= end.strftime("%Y%m%d"):
                    collected[raw_date] = item
                    valid_dates.append(datetime.strptime(raw_date, "%Y%m%d").date())
            if not valid_dates:
                break
            next_end = min(valid_dates) - timedelta(days=1)
            if next_end >= cursor_end:
                break
            cursor_end = next_end
            time.sleep(0.55 if self.settings.kis_env.lower() in {"virtual", "paper", "demo"} else 0.10)
        return [collected[key] for key in sorted(collected)]

    def valuation_snapshot(self, code: str) -> dict[str, Any]:
        response = self._get(
            f"{self.settings.kis_base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=self._headers("FHKST01010100"),
            params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
            context="종목 가치지표 조회")
        payload = response.json()
        if payload.get("rt_cd") not in (None, "0"):
            raise RuntimeError(f"KIS 오류: {payload.get('msg1', payload)}")
        return payload.get("output", {})
