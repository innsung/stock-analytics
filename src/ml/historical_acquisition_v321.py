from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
import json
import os
import time
from typing import Protocol, Callable
from importlib.metadata import version as package_version, PackageNotFoundError

from dotenv import load_dotenv

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH, read_valuation_snapshot_csv

SOURCE = "KRX_PYKRX_EOD"
MIN_PYKRX_VERSION = (1, 2, 8)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0


@contextmanager
def _requests_timeout(seconds: float):
    """Inject a default requests timeout into pykrx calls without changing pykrx internals."""
    import requests
    original = requests.sessions.Session.request

    def request_with_timeout(session, method, url, **kwargs):
        kwargs.setdefault("timeout", seconds)
        return original(session, method, url, **kwargs)

    requests.sessions.Session.request = request_with_timeout
    try:
        yield
    finally:
        requests.sessions.Session.request = original


@contextmanager
def _quiet_provider_output():
    """Prevent third-party login messages from exposing account IDs in logs."""
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        yield


def _year_chunks(start: str, end: str) -> list[tuple[str, str]]:
    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    chunks: list[tuple[str, str]] = []
    for year in range(start_dt.year, end_dt.year + 1):
        left = max(start_dt, datetime(year, 1, 1))
        right = min(end_dt, datetime(year, 12, 31))
        chunks.append((left.strftime("%Y%m%d"), right.strftime("%Y%m%d")))
    return chunks


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class HistoricalMarketProvider(Protocol):
    def fundamentals(self, start: str, end: str, code: str, frequency: str) -> pd.DataFrame: ...
    def market_cap(self, start: str, end: str, code: str, frequency: str) -> pd.DataFrame: ...
    def ohlcv(self, start: str, end: str, code: str, frequency: str) -> pd.DataFrame: ...
    def index_constituents(self, index_code: str, date: str) -> list[str]: ...


class PykrxProvider:
    """Authenticated KRX adapter for the 2026 login policy."""
    def __init__(self, request_timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.request_timeout = float(request_timeout)
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        try:
            installed = package_version("pykrx")
        except PackageNotFoundError as exc:
            raise RuntimeError(
                "pykrx가 설치되어 있지 않습니다. `python -m pip install \"pykrx>=1.2.8,<2\"` 후 다시 실행하세요."
            ) from exc
        parts = tuple(int(x) for x in installed.split("+")[0].split(".")[:3])
        if parts < MIN_PYKRX_VERSION:
            raise RuntimeError(
                f"pykrx {installed}은 2026 KRX 로그인 정책 대응 버전보다 낮습니다. "
                "`python -m pip install --upgrade \"pykrx>=1.2.8,<2\"`를 실행하세요."
            )
        missing = [name for name in ("KRX_ID", "KRX_PW") if not os.getenv(name, "").strip()]
        if missing:
            raise RuntimeError(
                "KRX 자격증명이 없습니다: " + ", ".join(missing) +
                ". 프로젝트 루트의 .env에 KRX_ID와 KRX_PW를 저장하세요. 값은 로그에 출력하지 않습니다."
            )
        try:
            with _quiet_provider_output():
                from pykrx import stock  # type: ignore
        except ImportError as exc:
            raise RuntimeError("pykrx import에 실패했습니다.") from exc
        self.stock = stock
        self.installed_version = installed

    def preflight(self, code: str, end: str) -> dict:
        """Make one small authenticated request before a long acquisition run."""
        end_dt = datetime.strptime(end, "%Y%m%d")
        start_dt = end_dt - timedelta(days=14)
        probe_start = start_dt.strftime("%Y%m%d")
        try:
            with _quiet_provider_output(), _requests_timeout(self.request_timeout):
                frame = self.stock.get_market_fundamental(probe_start, end, code, freq="d")
        except Exception as exc:
            return {
                "ok": False, "provider": SOURCE, "pykrx_version": self.installed_version,
                "credentials_present": True, "probe_code": code, "probe_end": end,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if frame is None or frame.empty:
            return {
                "ok": False, "provider": SOURCE, "pykrx_version": self.installed_version,
                "credentials_present": True, "probe_code": code, "probe_end": end,
                "error": "KRX 인증 요청은 완료됐지만 probe 데이터가 비어 있습니다. ID/PW 또는 KRX 세션 상태를 확인하세요.",
            }
        return {
            "ok": True, "provider": SOURCE, "pykrx_version": self.installed_version,
            "credentials_present": True, "probe_code": code, "probe_end": end,
            "rows": int(len(frame)), "error": "",
        }

    def fundamentals(self, start: str, end: str, code: str, frequency: str) -> pd.DataFrame:
        with _quiet_provider_output(), _requests_timeout(self.request_timeout):
            return self.stock.get_market_fundamental(start, end, code, freq=frequency)

    def market_cap(self, start: str, end: str, code: str, frequency: str) -> pd.DataFrame:
        with _quiet_provider_output(), _requests_timeout(self.request_timeout):
            return self.stock.get_market_cap(start, end, code, freq=frequency)

    def ohlcv(self, start: str, end: str, code: str, frequency: str) -> pd.DataFrame:
        with _quiet_provider_output(), _requests_timeout(self.request_timeout):
            return self.stock.get_market_ohlcv(start, end, code, freq=frequency, adjusted=True)

    def index_constituents(self, index_code: str, date: str) -> list[str]:
        # pykrx versions differ in argument order; support both without guessing silently.
        fn = self.stock.get_index_portfolio_deposit_file
        with _quiet_provider_output(), _requests_timeout(self.request_timeout):
            try:
                values = fn(index_code, date)
            except TypeError:
                values = fn(index_code, date=date)
        if isinstance(values, pd.DataFrame):
            return [str(x).zfill(6) for x in values.index.tolist()]
        return [str(x).zfill(6) for x in list(values)]


def _yyyymmdd(value: str) -> str:
    value = str(value).replace("-", "").strip()
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"날짜는 YYYYMMDD 형식이어야 합니다: {value!r}")
    return value


def _col(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return frame[name]
    return pd.Series(index=frame.index, dtype=float)


def _normalize_index(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.index = pd.to_datetime(out.index)
    out.index.name = "date"
    return out.sort_index()


def _read_codes(path: str) -> list[str]:
    frame = pd.read_csv(path, dtype=str).fillna("")
    if "code" not in frame.columns:
        raise ValueError("--universe-csv에는 code 열이 필요합니다.")
    if "enabled" in frame.columns:
        enabled = frame["enabled"].str.lower().isin({"1", "true", "yes", "y"})
        frame = frame[enabled]
    return list(dict.fromkeys(frame["code"].str.strip().str.zfill(6).tolist()))


def _fetch_valuation_chunk(
    provider: HistoricalMarketProvider, code: str, start: str, end: str, frequency: str
) -> pd.DataFrame:
    f = _normalize_index(provider.fundamentals(start, end, code, frequency))
    c = _normalize_index(provider.market_cap(start, end, code, frequency))
    p = _normalize_index(provider.ohlcv(start, end, code, frequency))
    merged = f.join(c, how="outer", rsuffix="_cap").join(p, how="outer", rsuffix="_px")
    columns = ["code", "snapshot_date", "price", "market_cap", "per", "pbr", "eps", "bps", "dividend_yield", "known_at", "source"]
    if merged.empty:
        return pd.DataFrame(columns=columns)
    out = pd.DataFrame(index=merged.index)
    out["code"] = code
    out["snapshot_date"] = out.index.strftime("%Y%m%d")
    out["price"] = pd.to_numeric(_col(merged, "종가", "Close", "close"), errors="coerce")
    out["market_cap"] = pd.to_numeric(_col(merged, "시가총액", "Market Cap", "market_cap"), errors="coerce")
    out["per"] = pd.to_numeric(_col(merged, "PER", "per"), errors="coerce")
    out["pbr"] = pd.to_numeric(_col(merged, "PBR", "pbr"), errors="coerce")
    out["eps"] = pd.to_numeric(_col(merged, "EPS", "eps"), errors="coerce")
    out["bps"] = pd.to_numeric(_col(merged, "BPS", "bps"), errors="coerce")
    out["dividend_yield"] = pd.to_numeric(_col(merged, "DIV", "배당수익률", "dividend_yield"), errors="coerce")
    out["known_at"] = out["snapshot_date"]
    out["source"] = SOURCE
    out = out[out["snapshot_date"] <= RESEARCH_SEEN_THROUGH]
    out = out.dropna(subset=["price", "market_cap"])
    return out.reset_index(drop=True)[columns]


def acquire_valuation_history(
    provider: HistoricalMarketProvider,
    codes: list[str],
    start: str,
    end: str,
    frequency: str = "m",
    sleep_seconds: float = 0.15,
    checkpoint_dir: str | Path | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    resume: bool = True,
    progress: Callable[[str], None] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Annual, resumable valuation acquisition. A completed chunk is never requested twice when resume=True."""
    columns = ["code", "snapshot_date", "price", "market_cap", "per", "pbr", "eps", "bps", "dividend_yield", "known_at", "source"]
    chunks = _year_chunks(start, end)
    checkpoint_root = Path(checkpoint_dir) if checkpoint_dir else None
    if checkpoint_root:
        checkpoint_root.mkdir(parents=True, exist_ok=True)
    all_frames: list[pd.DataFrame] = []
    audit: list[dict] = []
    total_units = len(codes) * len(chunks)
    unit = 0
    emit = progress or (lambda _msg: None)

    for code_idx, code in enumerate(codes, start=1):
        for chunk_idx, (chunk_start, chunk_end) in enumerate(chunks, start=1):
            unit += 1
            year = chunk_start[:4]
            key = f"{code}_{chunk_start}_{chunk_end}"
            csv_path = checkpoint_root / f"{key}.csv" if checkpoint_root else None
            done_path = checkpoint_root / f"{key}.done.json" if checkpoint_root else None
            prefix = f"[{code_idx}/{len(codes)}] {code} [{chunk_idx}/{len(chunks)}] {year} ({unit}/{total_units})"

            if resume and csv_path and done_path and csv_path.exists() and done_path.exists():
                try:
                    cached = pd.read_csv(csv_path, dtype={"code": str})
                    cached = cached.reindex(columns=columns)
                except pd.errors.EmptyDataError:
                    cached = pd.DataFrame(columns=columns)
                all_frames.append(cached)
                meta = json.loads(done_path.read_text(encoding="utf-8"))
                audit.append({"code": code, "chunk_start": chunk_start, "chunk_end": chunk_end,
                              "status": "RESUMED", "rows": int(meta.get("rows", len(cached))),
                              "attempts": 0, "error": ""})
                emit(f"{prefix} RESUME/SKIP {len(cached):,}행")
                continue

            last_error = ""
            frame = pd.DataFrame(columns=columns)
            success = False
            for attempt in range(1, max(1, int(max_retries)) + 1):
                emit(f"{prefix} 조회 시도 {attempt}/{max(1, int(max_retries))}...")
                try:
                    frame = _fetch_valuation_chunk(provider, code, chunk_start, chunk_end, frequency)
                    success = True
                    break
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    emit(f"{prefix} 실패: {last_error}")
                    if attempt < max(1, int(max_retries)):
                        wait = max(0.0, float(retry_backoff_seconds)) * (2 ** (attempt - 1))
                        emit(f"{prefix} {wait:.1f}초 후 재시도")
                        if wait:
                            time.sleep(wait)

            if success:
                all_frames.append(frame)
                if csv_path and done_path:
                    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
                    _atomic_write_json(done_path, {"code": code, "chunk_start": chunk_start, "chunk_end": chunk_end,
                                                   "rows": len(frame), "completed_at": datetime.now().isoformat(timespec="seconds")})
                status = "OK" if len(frame) else "NO_DATA"
                audit.append({"code": code, "chunk_start": chunk_start, "chunk_end": chunk_end,
                              "status": status, "rows": len(frame), "attempts": attempt, "error": ""})
                emit(f"{prefix} {status} {len(frame):,}행 / checkpoint 저장")
            else:
                audit.append({"code": code, "chunk_start": chunk_start, "chunk_end": chunk_end,
                              "status": "ERROR", "rows": 0, "attempts": max(1, int(max_retries)), "error": last_error})
                emit(f"{prefix} ERROR / 다음 chunk로 계속")

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    result = pd.concat(all_frames, ignore_index=True)[columns] if all_frames else pd.DataFrame(columns=columns)
    if not result.empty:
        result["code"] = result["code"].astype(str).str.zfill(6)
        result = result.drop_duplicates(["code", "snapshot_date"], keep="last").sort_values(["snapshot_date", "code"])
    return result, pd.DataFrame(audit)


def acquire_index_universe_observations(
    provider: HistoricalMarketProvider,
    index_code: str,
    dates: list[str],
    sleep_seconds: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    audit: list[dict] = []
    for date in dates:
        try:
            codes = provider.index_constituents(index_code, date)
            for code in codes:
                rows.append({"observation_date": date, "code": code, "index_code": index_code, "known_at": date, "source": SOURCE})
            audit.append({"date": date, "status": "OK" if codes else "EMPTY", "rows": len(codes), "error": ""})
        except Exception as exc:
            audit.append({"date": date, "status": "ERROR", "rows": 0, "error": f"{type(exc).__name__}: {exc}"})
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return pd.DataFrame(rows, columns=["observation_date", "code", "index_code", "known_at", "source"]), pd.DataFrame(audit)


def _observation_dates(valuation: pd.DataFrame) -> list[str]:
    if valuation.empty:
        return []
    return sorted(valuation["snapshot_date"].dropna().astype(str).unique().tolist())




def check_krx_provider_v321(code: str = "005930", end: str = RESEARCH_SEEN_THROUGH, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Credential-safe provider check. Secrets are never returned."""
    end = _yyyymmdd(end)
    if end > RESEARCH_SEEN_THROUGH:
        raise ValueError(f"연구 경계 {RESEARCH_SEEN_THROUGH} 이후 날짜는 provider 검사에 사용하지 않습니다.")
    provider = PykrxProvider(request_timeout=timeout_seconds)
    result = provider.preflight(str(code).strip().zfill(6), end)
    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "KRX provider preflight 실패")
    return result


def acquire_historical_data_v321(
    universe_csv: str,
    start: str,
    end: str,
    output_dir: str,
    frequency: str = "m",
    index_code: str | None = None,
    provider: HistoricalMarketProvider | None = None,
    sleep_seconds: float = 0.15,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    resume: bool = True,
    progress: Callable[[str], None] | None = print,
) -> dict:
    start, end = _yyyymmdd(start), _yyyymmdd(end)
    if start > end:
        raise ValueError("--start는 --end보다 늦을 수 없습니다.")
    if end > RESEARCH_SEEN_THROUGH:
        raise ValueError(f"연구 경계 {RESEARCH_SEEN_THROUGH} 이후 데이터 수집은 V3.2.1 재튜닝 입력으로 금지됩니다.")
    if frequency not in {"d", "m"}:
        raise ValueError("--frequency는 d 또는 m만 허용합니다.")
    source_path = Path(universe_csv)
    if not source_path.exists():
        raise FileNotFoundError(f"유니버스 파일이 없습니다: {source_path}")
    codes = _read_codes(str(source_path))
    if not codes:
        raise ValueError("수집할 종목이 없습니다.")
    if timeout_seconds <= 0:
        raise ValueError("--timeout-seconds는 0보다 커야 합니다.")
    if max_retries < 1:
        raise ValueError("--max-retries는 1 이상이어야 합니다.")
    provider = provider or PykrxProvider(request_timeout=timeout_seconds)
    provider_status = {"ok": True, "provider": type(provider).__name__, "preflight": "CUSTOM_PROVIDER_SKIPPED"}
    if isinstance(provider, PykrxProvider):
        provider_status = provider.preflight(codes[0], end)
        if not provider_status.get("ok"):
            raise RuntimeError(
                "KRX provider 사전검사 실패. 장시간 수집을 시작하지 않습니다. "
                + str(provider_status.get("error", "unknown error"))
            )
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "provider_status.json").write_text(
        json.dumps(provider_status, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoint_dir = target / "checkpoints" / "valuation"
    valuation, valuation_audit = acquire_valuation_history(
        provider, codes, start, end, frequency, sleep_seconds, checkpoint_dir=checkpoint_dir,
        max_retries=max_retries, retry_backoff_seconds=retry_backoff_seconds, resume=resume, progress=progress)
    valuation_path = target / "valuation_snapshots.csv"
    valuation.to_csv(valuation_path, index=False, encoding="utf-8-sig")
    valuation_audit.to_csv(target / "valuation_acquisition_audit.csv", index=False, encoding="utf-8-sig")

    strict_verified = False
    strict_status = "VALUATION_SNAPSHOT_INPUT_NOT_AVAILABLE"
    if not valuation.empty:
        _, strict_verified, strict_status = read_valuation_snapshot_csv(str(valuation_path))
    failed_chunks = int((valuation_audit.get("status", pd.Series(dtype=str)) == "ERROR").sum())
    resumed_chunks = int((valuation_audit.get("status", pd.Series(dtype=str)) == "RESUMED").sum())
    acquisition_complete = failed_chunks == 0
    if not acquisition_complete:
        strict_verified = False
        strict_status = "VALUATION_SNAPSHOT_INPUT_PARTIAL_CHUNK_FAILURE"

    universe_rows = 0
    universe_status = "NOT_REQUESTED"
    if index_code:
        observations, universe_audit = acquire_index_universe_observations(
            provider, index_code, _observation_dates(valuation), sleep_seconds)
        observations.to_csv(target / "universe_observations.csv", index=False, encoding="utf-8-sig")
        universe_audit.to_csv(target / "universe_acquisition_audit.csv", index=False, encoding="utf-8-sig")
        universe_rows = len(observations)
        universe_status = "OBSERVATIONS_ONLY_NOT_CANONICAL_INTERVALS" if universe_rows else "NO_UNIVERSE_DATA"

    # Explicitly do not fabricate datasets we cannot prove from these endpoints.
    blockers = {
        "total_return": "NOT_ACQUIRED: adjusted OHLCV is not equivalent to dividend-inclusive total return",
        "corporate_actions": "NOT_ACQUIRED: disclosure/effective-date reconciliation required before canonical use",
        "universe_history": universe_status,
    }
    manifest = {
        "phase": "V3.2.1 Historical Data Acquisition Phase 4.2",
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "provider": SOURCE,
        "provider_status": provider_status,
        "requested_period": [start, end],
        "frequency": frequency,
        "chunking": "ANNUAL",
        "request_timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
        "retry_backoff_seconds": retry_backoff_seconds,
        "resume_enabled": bool(resume),
        "checkpoint_dir": checkpoint_dir.as_posix(),
        "requested_codes": len(codes),
        "valuation_rows": len(valuation),
        "valuation_codes": int(valuation["code"].nunique()) if not valuation.empty else 0,
        "valuation_strict_status": strict_status,
        "valuation_strict_verified": bool(strict_verified),
        "acquisition_complete": bool(acquisition_complete),
        "failed_chunks": failed_chunks,
        "resumed_chunks": resumed_chunks,
        "universe_observation_rows": universe_rows,
        "blockers": blockers,
        "next_command": f"python -m src.main import-valuation-snapshots-v321 --csv {valuation_path.as_posix()}",
        "note": "No current-value backfill, interpolation, dividend-total-return fabrication, or post-cutoff acquisition is performed.",
    }
    (target / "acquisition_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
