from __future__ import annotations

from pathlib import Path
import json
import sqlite3

import numpy as np
import pandas as pd

from src.ml.data_integrity_v321 import (
    RESEARCH_SEEN_THROUGH,
    read_corporate_actions_csv_v321,
    read_total_return_csv_v321,
)

SUPPORTED_DERIVED_ACTIONS = {
    "SPLIT", "REVERSE_SPLIT", "BONUS", "CASH_DIVIDEND", "ETF_DISTRIBUTION"
}


def _load_coverage(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Total Return coverage JSON이 없습니다: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    required = {
        "start", "end", "codes", "cash_distributions_complete",
        "capital_actions_complete", "complex_actions_complete",
        "coverage_gate_status", "source",
    }
    missing = required - set(data)
    if missing:
        raise ValueError("coverage JSON 누락 필드: " + ", ".join(sorted(missing)))
    data["start"] = str(data["start"]).replace("-", "")
    data["end"] = str(data["end"]).replace("-", "")
    data["codes"] = [str(x).zfill(6) for x in data["codes"]]
    if data["end"] > RESEARCH_SEEN_THROUGH:
        raise ValueError(f"coverage end가 연구 경계 {RESEARCH_SEEN_THROUGH} 이후입니다.")
    if data["coverage_gate_status"] != "PASS" or not data["complex_actions_complete"]:
        raise ValueError(
            "Total Return VERIFIED 생성에는 PASS 상태의 complex-action coverage gate가 필요합니다."
        )
    if not data["cash_distributions_complete"] or not data["capital_actions_complete"]:
        raise ValueError("Total Return VERIFIED 생성에는 cash_distributions_complete와 capital_actions_complete가 모두 true여야 합니다.")
    if not str(data["source"]).strip():
        raise ValueError("coverage source가 필요합니다.")
    return data


def build_total_return_history_v321(conn: sqlite3.Connection, *, corporate_actions_csv: str,
                                    coverage_json: str, output_csv: str,
                                    benchmark_code: str = "069500") -> dict:
    coverage = _load_coverage(coverage_json)
    actions, verified_actions, action_status = read_corporate_actions_csv_v321(corporate_actions_csv)
    if not verified_actions:
        bad = int((~actions["row_valid"]).sum()) if not actions.empty else 0
        raise ValueError(f"기업행사 입력 검증 실패: {action_status}, invalid_rows={bad}")
    unsupported = sorted(set(actions["action_type"]) - SUPPORTED_DERIVED_ACTIONS)
    if unsupported:
        raise ValueError(
            "가격+기업행사로 안전하게 파생할 수 없는 action_type이 있습니다: " + ", ".join(unsupported)
            + ". 외부 검증 total-return index를 사용하세요."
        )
    codes = list(dict.fromkeys([*coverage["codes"], str(benchmark_code).zfill(6)]))
    rows = []
    audit = []
    for code in codes:
        prices = pd.read_sql_query(
            "SELECT date,close FROM stock_prices WHERE code=? AND date BETWEEN ? AND ? ORDER BY date",
            conn, params=(code, coverage["start"], coverage["end"]), dtype={"date": str})
        if prices.empty:
            audit.append({"code": code, "status": "NO_PRICE", "rows": 0})
            continue
        prices["date"] = prices["date"].astype(str).str.replace("-", "", regex=False)
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices = prices.dropna(subset=["close"])
        a = actions[actions["code"] == code].copy()
        event_map = {}
        for r in a.itertuples(index=False):
            d = str(r.effective_date)
            item = event_map.setdefault(d, {"factor": 1.0, "cash": 0.0, "known_at": d})
            item["factor"] *= float(r.adjustment_factor)
            item["cash"] += float(r.cash_amount)
            item["known_at"] = max(item["known_at"], str(r.known_at))
        tri = 100.0
        previous = None
        code_rows = 0
        for r in prices.itertuples(index=False):
            date = str(r.date)
            close = float(r.close)
            if previous is not None:
                event = event_map.get(date, {"factor": 1.0, "cash": 0.0})
                gross = (close * float(event["factor"]) + float(event["cash"])) / previous
                if not np.isfinite(gross) or gross <= 0:
                    raise ValueError(f"비정상 total-return gross factor: {code} {date} {gross}")
                tri *= gross
            rows.append({
                "code": code, "date": date, "total_return_index": tri,
                "known_at": date, "source": f"DERIVED_FROM_STOCK_PRICES_AND_VERIFIED_ACTIONS:{coverage['source']}",
            })
            previous = close
            code_rows += 1
        audit.append({"code": code, "status": "OK", "rows": code_rows})
    frame = pd.DataFrame(rows)
    missing_codes = sorted(set(codes) - set(frame["code"].unique() if not frame.empty else []))
    if missing_codes:
        raise ValueError("Total Return 가격 coverage 누락 종목: " + ", ".join(missing_codes))
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False, encoding="utf-8-sig")
    verified_frame, verified, status = read_total_return_csv_v321(str(out))
    if not verified:
        out.unlink(missing_ok=True)
        raise RuntimeError(f"생성 Total Return canonical 검증 실패: {status}")
    audit_path = out.with_name(out.stem + "_build_audit.csv")
    pd.DataFrame(audit).to_csv(audit_path, index=False, encoding="utf-8-sig")
    manifest_path = out.with_name(out.stem + "_manifest.json")
    manifest_path.write_text(json.dumps({
        "status": status,
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "rows": len(verified_frame),
        "codes": int(verified_frame["code"].nunique()),
        "first_date": verified_frame["date"].min(),
        "last_date": verified_frame["date"].max(),
        "coverage": coverage,
        "formula": "TR_t = TR_(t-1) * ((close_t * share_adjustment_factor_t + cash_distribution_t) / close_(t-1))",
        "unsupported_complex_actions_rejected": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": status, "rows": len(verified_frame), "codes": int(verified_frame["code"].nunique()),
        "output_csv": str(out), "audit_csv": str(audit_path), "manifest_json": str(manifest_path),
    }
