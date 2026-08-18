from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol
import json
import math
import re

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

SUPPORTED_MARKET_FACTOR_ACTIONS = {"BONUS", "SPLIT", "REVERSE_SPLIT"}


class MarketAdjustmentProvider(Protocol):
    def ohlcv(self, start: str, end: str, code: str, adjusted: bool) -> pd.DataFrame: ...


class PykrxMarketAdjustmentProvider:
    """KRX market-price adapter.

    Uses pykrx adjusted=False/True series. If the installed pykrx/provider no
    longer supports this contract, fail instead of silently treating one series
    as the other.
    """
    def __init__(self):
        from pykrx import stock
        self.stock = stock

    def ohlcv(self, start: str, end: str, code: str, adjusted: bool) -> pd.DataFrame:
        try:
            return self.stock.get_market_ohlcv_by_date(
                start, end, code, adjusted=bool(adjusted)
            )
        except TypeError as exc:
            raise RuntimeError(
                "현재 pykrx가 adjusted=True/False OHLCV 비교를 지원하지 않습니다. "
                "동일 계열을 strict evidence로 위장하지 않습니다."
            ) from exc


def _clean_date(value) -> str:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return digits if len(digits) == 8 else ""


def _normalize_close(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["date", "close"])
    f = frame.copy()
    if not isinstance(f.index, pd.RangeIndex):
        f = f.reset_index()
    date_col = next((c for c in f.columns if str(c).lower() in {"날짜", "date", "index"}), f.columns[0])
    close_col = next((c for c in f.columns if str(c).lower() in {"종가", "close"}), None)
    if close_col is None:
        raise ValueError("OHLCV 응답에서 종가(close/종가) 열을 찾을 수 없습니다.")
    out = pd.DataFrame({
        "date": pd.to_datetime(f[date_col], errors="coerce").dt.strftime("%Y%m%d"),
        "close": pd.to_numeric(f[close_col], errors="coerce"),
    }).dropna()
    return out[out["close"] > 0].drop_duplicates("date").sort_values("date")


def _window(center: str, days: int) -> tuple[str, str]:
    dt = datetime.strptime(center, "%Y%m%d")
    return (
        (dt - timedelta(days=int(days))).strftime("%Y%m%d"),
        min(dt + timedelta(days=int(days)), datetime.strptime(RESEARCH_SEEN_THROUGH, "%Y%m%d")).strftime("%Y%m%d"),
    )


def detect_adjustment_breakpoints_v321(
    provider: MarketAdjustmentProvider,
    *,
    code: str,
    center_date: str,
    window_days: int = 20,
    ratio_tolerance: float = 0.002,
) -> pd.DataFrame:
    """Find dates where adjusted/raw close ratio changes materially.

    A breakpoint is market evidence of a historical price-adjustment boundary.
    It is not, by itself, evidence of the legal corporate-action type.
    """
    center = _clean_date(center_date)
    if len(center) != 8:
        return pd.DataFrame()
    start, end = _window(center, window_days)
    raw = _normalize_close(provider.ohlcv(start, end, str(code).zfill(6), adjusted=False))
    adj = _normalize_close(provider.ohlcv(start, end, str(code).zfill(6), adjusted=True))
    if raw.empty or adj.empty:
        return pd.DataFrame()

    m = raw.merge(adj, on="date", suffixes=("_raw", "_adj"))
    if len(m) < 2:
        return pd.DataFrame()
    m["ratio"] = m["close_adj"] / m["close_raw"]
    m["previous_ratio"] = m["ratio"].shift(1)
    m["ratio_change"] = m["ratio"] / m["previous_ratio"]
    m["distance_days"] = (
        pd.to_datetime(m["date"], format="%Y%m%d") - pd.to_datetime(center, format="%Y%m%d")
    ).abs().dt.days
    # Ignore tiny rounding differences.
    bp = m[
        m["previous_ratio"].notna()
        & (m["ratio_change"] - 1.0).abs().gt(float(ratio_tolerance))
    ].copy()
    return bp[[
        "date", "ratio", "previous_ratio", "ratio_change", "distance_days",
        "close_raw", "close_adj",
    ]].sort_values(["distance_days", "date"])


def build_market_adjustment_evidence_v321(
    provider: MarketAdjustmentProvider,
    *,
    official_candidates_csv: str,
    output_csv: str,
    audit_csv: str,
    window_days: int = 20,
    max_match_distance_days: int = 10,
    ratio_tolerance: float = 0.002,
) -> dict:
    """Convert uniquely matched KRX adjustment breakpoints into strict evidence.

    Only BONUS/SPLIT/REVERSE_SPLIT candidates are eligible. MERGER/SPINOFF and
    all cash distributions remain unresolved because raw/adjusted price ratios
    alone do not prove the economically correct treatment.
    """
    p = Path(official_candidates_csv)
    if not p.exists():
        raise FileNotFoundError(f"official candidate CSV가 없습니다: {p}")
    c = pd.read_csv(p, dtype=str).fillna("")
    required = {
        "code", "official_known_at", "official_event_date", "action_type_hint",
        "verification_source", "verification_reference",
    }
    missing = required - set(c.columns)
    if missing:
        raise ValueError("official candidate CSV 누락 열: " + ", ".join(sorted(missing)))

    evidence_rows = []
    audit_rows = []
    for idx, r in c.iterrows():
        code = str(r["code"]).zfill(6)
        action = str(r["action_type_hint"]).upper().strip()
        event_date = _clean_date(r["official_event_date"])
        known_at = _clean_date(r["official_known_at"])
        status = "UNRESOLVED"
        reason = ""
        matches = pd.DataFrame()

        if action not in SUPPORTED_MARKET_FACTOR_ACTIONS:
            reason = "ACTION_NOT_SAFE_FOR_RATIO_AUTOVERIFICATION"
        elif len(event_date) != 8 or len(known_at) != 8:
            reason = "MISSING_OFFICIAL_DATE"
        elif known_at > event_date:
            reason = "KNOWN_AT_AFTER_OFFICIAL_EVENT_DATE"
        else:
            matches = detect_adjustment_breakpoints_v321(
                provider, code=code, center_date=event_date,
                window_days=window_days, ratio_tolerance=ratio_tolerance,
            )
            nearby = matches[matches["distance_days"] <= int(max_match_distance_days)].copy()
            # Require exactly one unique market breakpoint near the official candidate.
            if len(nearby) == 1:
                m = nearby.iloc[0]
                factor = float(m["ratio_change"])
                if math.isfinite(factor) and factor > 0 and abs(factor - 1.0) > ratio_tolerance:
                    effective = str(m["date"])
                    if known_at <= effective <= RESEARCH_SEEN_THROUGH:
                        evidence_rows.append({
                            "queue_event_id": "",
                            "code": code,
                            "event_family": "CORPORATE_ACTION",
                            "source_reference_date": event_date,
                            "effective_date": effective,
                            "known_at": known_at,
                            "action_type": action,
                            "adjustment_factor": factor,
                            "cash_amount": 0.0,
                            "verification_source": "KRX_PYKRX_ADJUSTED_RAW_RATIO+"
                                                   + str(r["verification_source"]),
                            "verification_reference": (
                                f"{str(r['verification_reference'])}"
                                f"|ratio:{float(m['previous_ratio']):.12g}->{float(m['ratio']):.12g}"
                            ),
                            "resolution_note": "UNIQUE_KRX_MARKET_ADJUSTMENT_BREAKPOINT_NEAR_OFFICIAL_CANDIDATE",
                        })
                        status = "VERIFIED_MARKET_FACTOR"
                        reason = ""
                    else:
                        reason = "BREAKPOINT_OUTSIDE_PIT_DATE_ORDER"
                else:
                    reason = "INVALID_RATIO_FACTOR"
            elif len(nearby) == 0:
                reason = "NO_KRX_ADJUSTMENT_BREAKPOINT"
            else:
                reason = f"AMBIGUOUS_KRX_BREAKPOINTS:{len(nearby)}"

        audit_rows.append({
            "candidate_row": idx + 2,
            "code": code,
            "action_type_hint": action,
            "official_event_date": event_date,
            "official_known_at": known_at,
            "breakpoints_found": int(len(matches)),
            "status": status,
            "reason": reason,
        })

    evidence = pd.DataFrame(evidence_rows, columns=[
        "queue_event_id", "code", "event_family", "source_reference_date",
        "effective_date", "known_at", "action_type", "adjustment_factor",
        "cash_amount", "verification_source", "verification_reference",
        "resolution_note",
    ])
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    evidence.to_csv(out, index=False, encoding="utf-8-sig")
    audit = pd.DataFrame(audit_rows)
    ap = Path(audit_csv)
    ap.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(ap, index=False, encoding="utf-8-sig")

    result = {
        "candidate_rows": int(len(c)),
        "strict_market_evidence_rows": int(len(evidence)),
        "unresolved_candidate_rows": int((audit["status"] != "VERIFIED_MARKET_FACTOR").sum()) if not audit.empty else 0,
        "output_csv": str(out),
        "audit_csv": str(ap),
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "note": "Cash dividends/distributions are intentionally not auto-resolved from price gaps.",
    }
    manifest = out.with_name(out.stem + "_manifest.json")
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["manifest"] = str(manifest)
    return result


def merge_strict_evidence_v321(*, evidence_csvs: list[str], output_csv: str) -> dict:
    """Merge strict evidence sources without silently deduplicating conflicting events."""
    frames = []
    for path in evidence_csvs:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"strict evidence CSV가 없습니다: {p}")
        f = pd.read_csv(p, dtype=str).fillna("")
        if not f.empty:
            f["_source_file"] = str(p)
            frames.append(f)
    if not frames:
        raise ValueError("병합할 strict evidence 행이 없습니다.")
    merged = pd.concat(frames, ignore_index=True)
    key = ["code", "event_family", "effective_date", "action_type"]
    dup = merged.duplicated(key, keep=False)
    if dup.any():
        # Exact duplicate payloads may be safely collapsed; conflicting payloads block.
        conflicts = []
        keep_rows = []
        for _, g in merged.groupby(key, dropna=False):
            payload_cols = [
                "known_at", "adjustment_factor", "cash_amount",
                "verification_source", "verification_reference",
            ]
            normalized = g[payload_cols].astype(str).drop_duplicates()
            if len(normalized) > 1:
                conflicts.append(g)
            else:
                keep_rows.append(g.iloc[[0]])
        if conflicts:
            raise ValueError(f"strict evidence 충돌 이벤트가 있습니다: {sum(len(x) for x in conflicts)}행")
        merged = pd.concat(keep_rows, ignore_index=True)
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    merged.drop(columns=["_source_file"], errors="ignore").to_csv(
        target, index=False, encoding="utf-8-sig"
    )
    return {"rows": int(len(merged)), "output_csv": str(target)}
