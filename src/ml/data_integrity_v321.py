from __future__ import annotations

from pathlib import Path
import json
import sqlite3

import numpy as np
import pandas as pd

RESEARCH_SEEN_THROUGH = "20260709"
VALUATION_COLUMNS = {
    "code", "snapshot_date", "price", "market_cap", "per", "pbr", "eps", "bps",
    "dividend_yield", "known_at", "source",
}


def _date(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.replace("-", "", regex=False).str.strip()


def read_valuation_snapshot_csv(path: str | None) -> tuple[pd.DataFrame, bool, str]:
    if not path:
        cols = [*sorted(VALUATION_COLUMNS), "row_valid"]
        return pd.DataFrame(columns=cols), False, "VALUATION_SNAPSHOT_INPUT_NOT_AVAILABLE"
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"밸류에이션 스냅샷 CSV가 없습니다: {source}")
    frame = pd.read_csv(source, dtype=str).fillna("")
    missing = VALUATION_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("밸류에이션 스냅샷 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    frame["snapshot_date"] = _date(frame["snapshot_date"])
    frame["known_at"] = _date(frame["known_at"])
    numeric = ["price", "market_cap", "per", "pbr", "eps", "bps", "dividend_yield"]
    for col in numeric:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    placeholder = frame["source"].str.upper().str.contains("REPLACE_WITH|PLACEHOLDER|EXAMPLE", regex=True)
    invalid = (
        frame["snapshot_date"].str.len().ne(8)
        | frame["known_at"].str.len().ne(8)
        | frame["known_at"].gt(frame["snapshot_date"])
        | frame["snapshot_date"].gt(RESEARCH_SEEN_THROUGH)
        | frame["source"].str.strip().eq("")
        | placeholder
        | frame["price"].isna() | frame["price"].le(0)
        | frame["market_cap"].isna() | frame["market_cap"].le(0)
        | frame.duplicated(["code", "snapshot_date"], keep=False)
    )
    frame["row_valid"] = ~invalid
    verified = bool(not frame.empty and frame["row_valid"].all())
    return frame, verified, "VERIFIED_VALUATION_SNAPSHOT_INPUT" if verified else "INVALID_VALUATION_SNAPSHOT_INPUT"


def import_valuation_snapshots(conn: sqlite3.Connection, path: str) -> dict:
    frame, verified, status = read_valuation_snapshot_csv(path)
    if not verified:
        bad = int((~frame["row_valid"]).sum()) if not frame.empty else 0
        raise ValueError(f"밸류에이션 스냅샷 입력이 엄격 검증을 통과하지 못했습니다: {status}, invalid_rows={bad}")
    rows = [
        (
            r.code, r.snapshot_date, float(r.price), float(r.market_cap),
            None if pd.isna(r.per) else float(r.per),
            None if pd.isna(r.pbr) else float(r.pbr),
            None if pd.isna(r.eps) else float(r.eps),
            None if pd.isna(r.bps) else float(r.bps),
            None if pd.isna(r.dividend_yield) else float(r.dividend_yield),
            str(r.source),
        )
        for r in frame.itertuples(index=False)
    ]
    conn.executemany(
        """INSERT INTO valuation_snapshots(
            code,snapshot_date,price,market_cap,per,pbr,eps,bps,dividend_yield,source
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(code,snapshot_date) DO UPDATE SET
            price=excluded.price, market_cap=excluded.market_cap, per=excluded.per,
            pbr=excluded.pbr, eps=excluded.eps, bps=excluded.bps,
            dividend_yield=excluded.dividend_yield, source=excluded.source""",
        rows,
    )
    conn.executemany(
        """INSERT INTO valuation_snapshot_meta(code,snapshot_date,known_at,source) VALUES(?,?,?,?)
           ON CONFLICT(code,snapshot_date) DO UPDATE SET known_at=excluded.known_at,source=excluded.source""",
        [(r.code, r.snapshot_date, r.known_at, str(r.source)) for r in frame.itertuples(index=False)],
    )
    conn.commit()
    return {
        "status": status,
        "rows": len(frame),
        "codes": int(frame["code"].nunique()),
        "first_snapshot": frame["snapshot_date"].min(),
        "last_snapshot": frame["snapshot_date"].max(),
        "research_seen_through": RESEARCH_SEEN_THROUGH,
    }


def selection_persistence_audit(holdings: pd.DataFrame, periods: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "scope", "top_fraction", "code", "name", "industry", "selected_periods",
        "total_periods", "held_rate", "max_consecutive_selections", "mean_score",
        "mean_score_percentile", "mean_forward_return", "positive_forward_rate",
        "mean_universe_excess", "mean_etf_excess", "positive_universe_excess_rate",
        "positive_etf_excess_rate", "persistent_flag", "persistent_but_supported",
    ]
    if holdings.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict] = []
    for (scope, fraction), group in holdings.groupby(["scope", "top_fraction"]):
        pg = periods[(periods["scope"] == scope) & (periods["top_fraction"] == fraction)].copy()
        total_periods = int(pg["feature_date"].nunique())
        bench = pg.set_index("feature_date")[["universe_equal_weight_return", "etf_return"]]
        all_dates = sorted(pg["feature_date"].unique())
        date_index = {d: i for i, d in enumerate(all_dates)}
        for code, cg in group.groupby("code"):
            cg = cg.sort_values("feature_date").copy()
            cg = cg.join(bench, on="feature_date")
            idxs = [date_index[d] for d in cg["feature_date"] if d in date_index]
            max_run = run = 0
            prev = None
            for idx in idxs:
                run = run + 1 if prev is not None and idx == prev + 1 else 1
                max_run = max(max_run, run)
                prev = idx
            universe_excess = cg["forward_return"] - cg["universe_equal_weight_return"]
            etf_excess = cg["forward_return"] - cg["etf_return"]
            held_rate = len(cg) / max(total_periods, 1)
            persistent = bool(held_rate >= .80)
            supported = bool(
                persistent
                and float((universe_excess > 0).mean()) >= .50
                and float((etf_excess > 0).mean()) >= .50
                and float(universe_excess.mean()) > 0
                and float(etf_excess.mean()) > 0
            )
            first = cg.iloc[0]
            rows.append({
                "scope": scope, "top_fraction": fraction, "code": str(code),
                "name": first.get("name", ""), "industry": first.get("industry", ""),
                "selected_periods": len(cg), "total_periods": total_periods,
                "held_rate": held_rate, "max_consecutive_selections": max_run,
                "mean_score": float(cg["score"].mean()),
                "mean_score_percentile": float(cg["score_percentile"].mean()) if "score_percentile" in cg else np.nan,
                "mean_forward_return": float(cg["forward_return"].mean()),
                "positive_forward_rate": float((cg["forward_return"] > 0).mean()),
                "mean_universe_excess": float(universe_excess.mean()),
                "mean_etf_excess": float(etf_excess.mean()),
                "positive_universe_excess_rate": float((universe_excess > 0).mean()),
                "positive_etf_excess_rate": float((etf_excess > 0).mean()),
                "persistent_flag": persistent,
                "persistent_but_supported": supported,
            })
    return pd.DataFrame(rows, columns=columns)


TOTAL_RETURN_COLUMNS = {"code", "date", "total_return_index", "known_at", "source"}
CORPORATE_ACTION_COLUMNS = {
    "code", "effective_date", "action_type", "adjustment_factor", "cash_amount", "known_at", "source",
}
UNIVERSE_COLUMNS = {
    "code", "effective_from", "effective_to", "selection_known_at", "listing_date",
    "delisting_date", "industry", "liquidity_eligible", "source",
}
PLACEHOLDER_PATTERN = r"REPLACE_WITH|PLACEHOLDER|EXAMPLE"


def _source_is_placeholder(frame: pd.DataFrame) -> pd.Series:
    return frame["source"].fillna("").astype(str).str.upper().str.contains(
        PLACEHOLDER_PATTERN, regex=True)


def read_total_return_csv_v321(path: str | None) -> tuple[pd.DataFrame, bool, str]:
    if not path:
        return pd.DataFrame(columns=[*sorted(TOTAL_RETURN_COLUMNS), "row_valid"]), False, "TOTAL_RETURN_INPUT_NOT_AVAILABLE"
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = TOTAL_RETURN_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("총수익률 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    frame["date"] = _date(frame["date"])
    frame["known_at"] = _date(frame["known_at"])
    frame["total_return_index"] = pd.to_numeric(frame["total_return_index"], errors="coerce")
    invalid = (
        frame["date"].str.len().ne(8) | frame["known_at"].str.len().ne(8)
        | frame["known_at"].gt(frame["date"]) | frame["date"].gt(RESEARCH_SEEN_THROUGH)
        | frame["total_return_index"].isna() | frame["total_return_index"].le(0)
        | frame["source"].str.strip().eq("") | _source_is_placeholder(frame)
        | frame.duplicated(["code", "date"], keep=False)
    )
    frame["row_valid"] = ~invalid
    verified = bool(not frame.empty and frame["row_valid"].all())
    return frame, verified, "VERIFIED_TOTAL_RETURN_INPUT" if verified else "INVALID_TOTAL_RETURN_INPUT"


def read_corporate_actions_csv_v321(path: str | None) -> tuple[pd.DataFrame, bool, str]:
    if not path:
        return pd.DataFrame(columns=[*sorted(CORPORATE_ACTION_COLUMNS), "row_valid"]), False, "CORPORATE_ACTION_INPUT_NOT_AVAILABLE"
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = CORPORATE_ACTION_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("기업행사 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    frame["effective_date"] = _date(frame["effective_date"])
    frame["known_at"] = _date(frame["known_at"])
    frame["adjustment_factor"] = pd.to_numeric(frame["adjustment_factor"], errors="coerce")
    frame["cash_amount"] = pd.to_numeric(frame["cash_amount"], errors="coerce").fillna(0.0)
    allowed = {"SPLIT", "REVERSE_SPLIT", "RIGHTS", "BONUS", "MERGER", "SPINOFF", "CASH_DIVIDEND", "ETF_DISTRIBUTION"}
    invalid = (
        frame["effective_date"].str.len().ne(8) | frame["known_at"].str.len().ne(8)
        | frame["known_at"].gt(frame["effective_date"]) | frame["effective_date"].gt(RESEARCH_SEEN_THROUGH)
        | ~frame["action_type"].isin(allowed) | frame["adjustment_factor"].isna()
        | frame["adjustment_factor"].le(0) | frame["cash_amount"].lt(0)
        | frame["source"].str.strip().eq("") | _source_is_placeholder(frame)
        | frame.duplicated(["code", "effective_date", "action_type"], keep=False)
    )
    frame["row_valid"] = ~invalid
    verified = bool(not frame.empty and frame["row_valid"].all())
    return frame, verified, "VERIFIED_CORPORATE_ACTION_INPUT" if verified else "INVALID_CORPORATE_ACTION_INPUT"


def read_universe_history_csv_v321(path: str | None) -> tuple[pd.DataFrame, bool, str]:
    if not path:
        return pd.DataFrame(columns=[*sorted(UNIVERSE_COLUMNS), "row_valid"]), False, "UNIVERSE_HISTORY_INPUT_NOT_AVAILABLE"
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = UNIVERSE_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("유니버스 이력 CSV 누락 열: " + ", ".join(sorted(missing)))
    frame["code"] = frame["code"].str.strip().str.zfill(6)
    for col in ("effective_from", "effective_to", "selection_known_at", "listing_date", "delisting_date"):
        frame[col] = _date(frame[col])
    liquidity = frame["liquidity_eligible"].str.lower().str.strip().map(
        {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False})
    required_bad = pd.Series(False, index=frame.index)
    for col in ("effective_from", "selection_known_at", "listing_date"):
        required_bad |= frame[col].str.len().ne(8)
    optional_bad = pd.Series(False, index=frame.index)
    for col in ("effective_to", "delisting_date"):
        optional_bad |= frame[col].ne("") & frame[col].str.len().ne(8)
    invalid = (
        required_bad | optional_bad | frame["effective_from"].gt(RESEARCH_SEEN_THROUGH)
        | frame["selection_known_at"].gt(frame["effective_from"])
        | frame["listing_date"].gt(frame["effective_from"])
        | (frame["effective_to"].ne("") & frame["effective_to"].lt(frame["effective_from"]))
        | (frame["delisting_date"].ne("") & frame["delisting_date"].lt(frame["listing_date"]))
        | liquidity.isna() | frame["source"].str.strip().eq("") | _source_is_placeholder(frame)
        | frame.duplicated(["code", "effective_from", "effective_to"], keep=False)
    )
    frame["liquidity_eligible"] = liquidity
    frame["row_valid"] = ~invalid
    verified = bool(not frame.empty and frame["row_valid"].all())
    return frame, verified, "VERIFIED_UNIVERSE_HISTORY_INPUT" if verified else "INVALID_UNIVERSE_HISTORY_INPUT"


def build_data_foundation_v321(*, valuation_csv: str | None, total_return_csv: str | None,
                               corporate_actions_csv: str | None, universe_history_csv: str | None,
                               output_dir: str) -> dict:
    """Validate and canonicalize externally sourced PIT files without inventing history."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    specs = [
        ("valuation", valuation_csv, read_valuation_snapshot_csv, "valuation_snapshots_v321.csv"),
        ("total_return", total_return_csv, read_total_return_csv_v321, "total_return_history_v321.csv"),
        ("corporate_actions", corporate_actions_csv, read_corporate_actions_csv_v321, "corporate_actions_v321.csv"),
        ("universe_history", universe_history_csv, read_universe_history_csv_v321, "universe_history_v321.csv"),
    ]
    audit_rows = []
    outputs = {}
    for kind, path, reader, filename in specs:
        frame, verified, status = reader(path)
        if path and not verified:
            bad = int((~frame["row_valid"]).sum()) if "row_valid" in frame else len(frame)
            raise ValueError(f"{kind} 입력이 엄격 검증을 통과하지 못했습니다: {status}, invalid_rows={bad}")
        out_path = ""
        if path and verified:
            clean = frame.drop(columns=["row_valid"], errors="ignore")
            out = target / filename
            clean.to_csv(out, index=False, encoding="utf-8-sig")
            out_path = str(out)
            outputs[kind] = out_path
        date_col = next((c for c in ("snapshot_date", "date", "effective_date", "effective_from") if c in frame), None)
        audit_rows.append({
            "dataset": kind, "status": status, "verified": verified, "rows": len(frame),
            "codes": int(frame["code"].nunique()) if "code" in frame and not frame.empty else 0,
            "first_date": frame[date_col].min() if date_col and not frame.empty else "",
            "last_date": frame[date_col].max() if date_col and not frame.empty else "",
            "output_path": out_path,
        })
    audit = pd.DataFrame(audit_rows)
    audit.to_csv(target / "foundation_audit.csv", index=False, encoding="utf-8-sig")
    manifest = {
        "phase": "V3.2.1 Data Integrity Phase 3",
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "all_four_verified": bool(len(outputs) == 4),
        "outputs": outputs,
        "diagnostic_args": {
            "universe_history_csv": outputs.get("universe_history", ""),
            "total_return_csv": outputs.get("total_return", ""),
            "corporate_actions_csv": outputs.get("corporate_actions", ""),
        },
        "note": "No historical values are backfilled, interpolated, or inferred. Only source-observed rows are accepted.",
    }
    (target / "foundation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest | {"audit": audit.to_dict("records")}
