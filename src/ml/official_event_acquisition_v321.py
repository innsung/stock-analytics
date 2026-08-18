from __future__ import annotations

from pathlib import Path
import json
import time

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

ENDPOINTS = {
    "fricDecsn": "BONUS_ISSUE_DECISION",
    "cmpMgDecsn": "MERGER_DECISION",
    "cmpDvDecsn": "COMPANY_DIVISION_DECISION",
    "cmpDvmgDecsn": "DIVISION_MERGER_DECISION",
    "stkExtrDecsn": "STOCK_EXCHANGE_TRANSFER_DECISION",
}


def _clean_date(value) -> str:
    return str(value or "").replace("-", "").replace(".", "").strip()


def _first(raw: dict, *keys: str) -> str:
    for key in keys:
        value = _clean_date(raw.get(key))
        if value:
            return value
    return ""


def _candidate_fields(endpoint: str, raw: dict) -> dict:
    """Extract only documented/raw fields; do not invent price-adjustment dates."""
    known_at = _first(raw, "bddd", "rcept_dt")
    event_date = ""
    factor_hint = ""
    action_hint = ""

    if endpoint == "fricDecsn":
        # OpenDART documents nstk_asstd (new-share record date) and
        # nstk_ascnt_ps_ostk (new shares allotted per common share).
        event_date = _first(raw, "nstk_asstd")
        action_hint = "BONUS"
        try:
            allot = float(str(raw.get("nstk_ascnt_ps_ostk", "")).replace(",", ""))
            if allot >= 0:
                factor_hint = str(1.0 + allot)
        except Exception:
            factor_hint = ""
    elif endpoint == "cmpDvDecsn":
        event_date = _first(raw, "dvdt", "abcr_nstkasstd")
        action_hint = "SPINOFF"
    elif endpoint == "cmpDvmgDecsn":
        event_date = _first(raw, "dvmgdt", "dvdt", "abcr_nstkasstd")
        action_hint = "SPINOFF"
    elif endpoint == "cmpMgDecsn":
        event_date = _first(raw, "mgdt", "mgsprpd")
        action_hint = "MERGER"
    elif endpoint == "stkExtrDecsn":
        event_date = _first(raw, "extrdt", "stktrfdt")
        action_hint = "MERGER"

    return {
        "official_known_at": known_at,
        "official_event_date": event_date,
        "action_type_hint": action_hint,
        "adjustment_factor_hint": factor_hint,
    }


def acquire_official_event_candidates_v321(
    dart_client,
    *,
    universe_csv: str,
    start: str,
    end: str,
    output_dir: str,
    max_retries: int = 3,
    retry_backoff_seconds: float = 1.0,
    sleep_seconds: float = 0.05,
) -> dict:
    """Acquire detailed OpenDART major-event rows as official candidates.

    Candidate rows are NOT strict evidence yet. In particular, record dates and
    corporate legal dates are not silently converted into ex/price-adjustment dates.
    """
    start = _clean_date(start)
    end = _clean_date(end)
    if len(start) != 8 or len(end) != 8 or start > end:
        raise ValueError("start/end 날짜 형식이 잘못되었습니다.")
    if end > RESEARCH_SEEN_THROUGH:
        end = RESEARCH_SEEN_THROUGH

    u = pd.read_csv(universe_csv, dtype=str).fillna("")
    if "code" not in u.columns:
        raise ValueError("universe CSV에는 code 열이 필요합니다.")
    if "enabled" in u.columns:
        enabled = u["enabled"].astype(str).str.lower().isin({"1", "true", "yes", "y"})
        u = u[enabled]
    codes = u["code"].str.strip().str.zfill(6).tolist()

    corp_map = dart_client.corp_code_map()
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    rows = []
    audit = []
    total = len(codes) * len(ENDPOINTS)
    progress = 0

    for ci, code in enumerate(codes, 1):
        corp_code = corp_map.get(code, "")
        if not corp_code:
            audit.append({
                "code": code, "endpoint": "", "status": "NO_DART_CORP_CODE",
                "rows": 0, "attempts": 0, "error": "",
            })
            continue

        for endpoint, event_kind in ENDPOINTS.items():
            progress += 1
            print(f"[{ci}/{len(codes)}] {code} [{endpoint}] ({progress}/{total}) OpenDART 상세 이벤트 조회...")
            result = None
            error = ""
            attempts = 0
            for attempt in range(1, max_retries + 1):
                attempts = attempt
                try:
                    result = dart_client.major_event(endpoint, corp_code, start, end)
                    break
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    if attempt < max_retries:
                        time.sleep(retry_backoff_seconds * (2 ** (attempt - 1)))

            if result is None:
                audit.append({
                    "code": code, "endpoint": endpoint, "status": "FAILED",
                    "rows": 0, "attempts": attempts, "error": error,
                })
                continue

            for raw in result:
                extracted = _candidate_fields(endpoint, raw)
                rcept_no = str(raw.get("rcept_no", ""))
                rows.append({
                    "code": code,
                    "corp_code": corp_code,
                    "endpoint": endpoint,
                    "event_kind": event_kind,
                    "rcept_no": rcept_no,
                    "official_known_at": extracted["official_known_at"],
                    "official_event_date": extracted["official_event_date"],
                    "action_type_hint": extracted["action_type_hint"],
                    "adjustment_factor_hint": extracted["adjustment_factor_hint"],
                    "cash_amount_hint": "",
                    "verification_source": f"OPENDART_{endpoint}",
                    "verification_reference": rcept_no,
                    "strict_evidence_ready": False,
                    "strict_block_reason": (
                        "OFFICIAL_CANDIDATE_ONLY_REQUIRES_EX_OR_PRICE_ADJUSTMENT_DATE_VERIFICATION"
                    ),
                    "raw_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
                })
            audit.append({
                "code": code, "endpoint": endpoint,
                "status": "OK", "rows": len(result), "attempts": attempts, "error": "",
            })
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    frame = pd.DataFrame(rows)
    audit_frame = pd.DataFrame(audit)
    candidate_path = target / "official_event_candidates_v321.csv"
    audit_path = target / "official_event_candidate_acquisition_audit.csv"
    frame.to_csv(candidate_path, index=False, encoding="utf-8-sig")
    audit_frame.to_csv(audit_path, index=False, encoding="utf-8-sig")

    failed = int((audit_frame["status"] == "FAILED").sum()) if not audit_frame.empty else 0
    manifest = {
        "phase": "V3.2.1 Phase 5.6",
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "start": start,
        "end": end,
        "codes": len(codes),
        "endpoint_requests": int(total),
        "candidate_rows": int(len(frame)),
        "failed_endpoint_requests": failed,
        "status": "OFFICIAL_EVENT_CANDIDATES_ACQUIRED" if failed == 0 else "OFFICIAL_EVENT_CANDIDATES_PARTIAL",
        "strict_evidence_rows": 0,
        "note": (
            "Detailed OpenDART rows are official candidates only. Record/legal dates "
            "are not automatically promoted to total-return effective dates."
        ),
        "outputs": {
            "candidates": str(candidate_path),
            "audit": str(audit_path),
        },
    }
    manifest_path = target / "official_event_candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest | {"manifest_path": str(manifest_path)}


def enrich_official_evidence_template_v321(
    *,
    evidence_template_csv: str,
    candidate_csv: str,
    output_csv: str,
) -> dict:
    """Attach OpenDART candidate metadata without falsely marking strict evidence."""
    e = pd.read_csv(evidence_template_csv, dtype=str).fillna("")
    c = pd.read_csv(candidate_csv, dtype=str).fillna("")
    if "code" not in e.columns:
        raise ValueError("evidence template에 code 열이 필요합니다.")
    if c.empty:
        out = e.copy()
        out["official_candidate_count"] = 0
        out["official_candidate_summary"] = ""
    else:
        c["code"] = c["code"].astype(str).str.zfill(6)
        summaries = {}
        for code, g in c.groupby("code"):
            parts = []
            for r in g.itertuples(index=False):
                parts.append(
                    f"{r.event_kind}|{r.official_event_date}|{r.official_known_at}|"
                    f"{r.action_type_hint}|{r.adjustment_factor_hint}|{r.verification_reference}"
                )
            summaries[code] = (len(g), " || ".join(parts))
        out = e.copy()
        out["code"] = out["code"].astype(str).str.zfill(6)
        out["official_candidate_count"] = out["code"].map(
            lambda x: summaries.get(x, (0, ""))[0]
        )
        out["official_candidate_summary"] = out["code"].map(
            lambda x: summaries.get(x, (0, ""))[1]
        )

    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, index=False, encoding="utf-8-sig")
    return {
        "rows": int(len(out)),
        "rows_with_candidates": int((out["official_candidate_count"].astype(int) > 0).sum()),
        "output_csv": str(target),
    }
