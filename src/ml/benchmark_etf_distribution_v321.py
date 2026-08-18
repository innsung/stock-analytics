from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import json
import re

import pandas as pd

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

DEFAULT_BENCHMARK = "069500"
DEFAULT_ISSUER = "Samsung Asset Management KODEX"
DEFAULT_PRODUCT_URL = "https://m.samsungfund.com/etf/product/view.do?id=2ETF01"
PLACEHOLDER = re.compile(r"REPLACE_WITH|PLACEHOLDER|EXAMPLE|TODO|TBD", re.I)


def _date(v) -> str:
    return str(v or "").replace("-", "").replace(".", "").strip()


def _queue_id(code: str, ex_date: str, amount: str) -> str:
    raw = f"ETF_DISTRIBUTION|{str(code).zfill(6)}|{ex_date}|{amount}"
    return "etf_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def prepare_benchmark_etf_distribution_template_v321(
    *,
    output_csv: str,
    code: str = DEFAULT_BENCHMARK,
    issuer: str = DEFAULT_ISSUER,
    product_url: str = DEFAULT_PRODUCT_URL,
) -> dict:
    """Create an empty official-distribution import sheet.

    No expected quarterly dates are generated. The issuer states a distribution
    policy, but policy dates are not treated as actual historical cash events.
    """
    columns = [
        "code", "record_date", "ex_date", "pay_date", "announced_at",
        "cash_amount", "currency", "issuer", "verification_source",
        "verification_reference", "source_url", "note",
    ]
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=columns).to_csv(target, index=False, encoding="utf-8-sig")
    manifest = {
        "phase": "V3.2.1 Phase 5.9",
        "code": str(code).zfill(6),
        "issuer": issuer,
        "product_url": product_url,
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "status": "EMPTY_OFFICIAL_ETF_DISTRIBUTION_TEMPLATE",
        "rule": "Do not infer actual events from stated quarterly distribution policy.",
        "required_for_strict": [
            "ex_date", "announced_at", "cash_amount",
            "verification_source", "verification_reference", "source_url",
        ],
    }
    m = target.with_name(target.stem + "_manifest.json")
    m.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_csv": str(target), "manifest": str(m)}


def validate_benchmark_etf_distributions_v321(
    *,
    official_csv: str,
    strict_evidence_csv: str,
    audit_csv: str,
    code: str = DEFAULT_BENCHMARK,
) -> dict:
    """Validate actual issuer/KRX ETF cash-distribution observations.

    `announced_at <= ex_date` is required for strict PIT use. If historical
    announcement evidence is unavailable before ex-date, the row is not strict PIT
    evidence and remains blocked.
    """
    p = Path(official_csv)
    if not p.exists():
        raise FileNotFoundError(f"ETF official distribution CSV가 없습니다: {p}")
    f = pd.read_csv(p, dtype=str).fillna("")
    required = {
        "code", "record_date", "ex_date", "pay_date", "announced_at",
        "cash_amount", "currency", "issuer", "verification_source",
        "verification_reference", "source_url",
    }
    missing = required - set(f.columns)
    if missing:
        raise ValueError("ETF distribution CSV 누락 열: " + ", ".join(sorted(missing)))
    if f.empty:
        raise ValueError("ETF distribution CSV가 비어 있습니다. 실제 공식 분배금 이력을 입력하세요.")

    expected_code = str(code).zfill(6)
    f["code"] = f["code"].astype(str).str.zfill(6)
    for c in ("record_date", "ex_date", "pay_date", "announced_at"):
        f[c] = f[c].map(_date)
    f["cash_amount"] = pd.to_numeric(
        f["cash_amount"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    f["currency"] = f["currency"].str.strip().str.upper()

    invalid_code = ~f["code"].eq(expected_code)
    bad_date = pd.Series(False, index=f.index)
    for c in ("ex_date", "announced_at"):
        bad_date |= f[c].str.len().ne(8) | ~f[c].str.isdigit()
    optional_bad = pd.Series(False, index=f.index)
    for c in ("record_date", "pay_date"):
        optional_bad |= f[c].ne("") & (f[c].str.len().ne(8) | ~f[c].str.isdigit())

    invalid = (
        invalid_code | bad_date | optional_bad
        | f["ex_date"].gt(RESEARCH_SEEN_THROUGH)
        | f["announced_at"].gt(f["ex_date"])
        | (f["record_date"].ne("") & f["record_date"].lt(f["ex_date"]))
        | (f["pay_date"].ne("") & f["pay_date"].lt(f["record_date"].where(f["record_date"].ne(""), f["ex_date"])))
        | f["cash_amount"].isna() | f["cash_amount"].le(0)
        | ~f["currency"].eq("KRW")
        | f["issuer"].str.strip().eq("")
        | f["verification_source"].str.strip().eq("")
        | f["verification_source"].str.contains(PLACEHOLDER)
        | f["verification_reference"].str.strip().eq("")
        | f["source_url"].str.strip().eq("")
        | f.duplicated(["code", "ex_date", "cash_amount"], keep=False)
    )

    audit = f[[
        "code", "record_date", "ex_date", "pay_date", "announced_at",
        "cash_amount", "verification_source", "verification_reference",
    ]].copy()
    audit["valid"] = ~invalid
    audit["error"] = invalid.map(lambda x: "INVALID_ETF_DISTRIBUTION_ROW" if x else "")
    ap = Path(audit_csv)
    ap.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(ap, index=False, encoding="utf-8-sig")
    if invalid.any():
        raise ValueError(
            f"ETF 분배금 strict 검증 실패: invalid_rows={int(invalid.sum())}, audit={ap}"
        )

    strict = pd.DataFrame({
        "queue_event_id": [
            _queue_id(r.code, r.ex_date, str(r.cash_amount))
            for r in f.itertuples(index=False)
        ],
        "code": f["code"],
        "event_family": "DIVIDEND_OR_DISTRIBUTION",
        "source_reference_date": f["record_date"].where(f["record_date"].ne(""), f["ex_date"]),
        "effective_date": f["ex_date"],
        "known_at": f["announced_at"],
        "action_type": "ETF_DISTRIBUTION",
        "adjustment_factor": 1.0,
        "cash_amount": f["cash_amount"],
        "verification_source": f["verification_source"],
        "verification_reference": f["verification_reference"],
        "resolution_note": "STRICT_OFFICIAL_BENCHMARK_ETF_DISTRIBUTION",
    })
    out = Path(strict_evidence_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    strict.to_csv(out, index=False, encoding="utf-8-sig")

    return {
        "strict_rows": int(len(strict)),
        "code": expected_code,
        "first_ex_date": str(strict["effective_date"].min()),
        "last_ex_date": str(strict["effective_date"].max()),
        "strict_evidence_csv": str(out),
        "audit_csv": str(ap),
    }


def inject_benchmark_etf_events_v321(
    *,
    strict_evidence_csv: str,
    verification_csv: str,
    queue_registry_csv: str,
    output_verification_csv: str,
    output_registry_csv: str,
) -> dict:
    """Add verified benchmark ETF events into the Phase 5.4 queue/registry.

    Existing 399 stock queue events are preserved byte-for-data semantics. ETF
    rows are appended with their own deterministic queue_event_ids so coverage can
    include the benchmark without pretending it came from OpenDART stock facts.
    """
    sp = Path(strict_evidence_csv)
    vp = Path(verification_csv)
    rp = Path(queue_registry_csv)
    for p in (sp, vp, rp):
        if not p.exists():
            raise FileNotFoundError(str(p))

    strict = pd.read_csv(sp, dtype=str).fillna("")
    v = pd.read_csv(vp, dtype=str).fillna("")
    reg = pd.read_csv(rp, dtype=str).fillna("")
    if strict.empty:
        raise ValueError("benchmark ETF strict evidence가 비어 있습니다.")

    existing_ids = set(v["queue_event_id"]) | set(reg["queue_event_id"])
    collision = existing_ids.intersection(set(strict["queue_event_id"]))
    if collision:
        raise ValueError("ETF queue_event_id 충돌: " + ", ".join(sorted(collision)[:5]))

    add_v = pd.DataFrame({
        "queue_event_id": strict["queue_event_id"],
        "code": strict["code"],
        "event_family": strict["event_family"],
        "source_reference_date": strict["source_reference_date"],
        "source_description": "Benchmark ETF official cash distribution",
        "resolution_status": "VERIFIED",
        "effective_date": strict["effective_date"],
        "known_at": strict["known_at"],
        "action_type": strict["action_type"],
        "adjustment_factor": strict["adjustment_factor"],
        "cash_amount": strict["cash_amount"],
        "verification_source": strict["verification_source"],
        "verification_reference": strict["verification_reference"],
        "resolution_note": strict["resolution_note"],
    })
    add_reg = pd.DataFrame({
        "code": strict["code"],
        "event_family": strict["event_family"],
        "source_reference_date": strict["source_reference_date"],
        "source_description": "Benchmark ETF official cash distribution",
        "candidate_cash_amount": strict["cash_amount"],
        "candidate_adjustment_factor": "1",
        "candidate_effective_date": strict["effective_date"],
        "candidate_known_at": strict["known_at"],
        "action_type": strict["action_type"],
        "verification_source": strict["verification_source"],
        "verification_status": "VERIFIED_BENCHMARK_ETF_DISTRIBUTION",
        "queue_event_id": strict["queue_event_id"],
    })

    # Keep any extra registry columns by reindexing.
    merged_v = pd.concat([v, add_v.reindex(columns=v.columns, fill_value="")], ignore_index=True)
    merged_reg = pd.concat([reg, add_reg.reindex(columns=reg.columns, fill_value="")], ignore_index=True)

    ov = Path(output_verification_csv)
    orp = Path(output_registry_csv)
    ov.parent.mkdir(parents=True, exist_ok=True)
    orp.parent.mkdir(parents=True, exist_ok=True)
    merged_v.to_csv(ov, index=False, encoding="utf-8-sig")
    merged_reg.to_csv(orp, index=False, encoding="utf-8-sig")

    return {
        "original_verification_rows": int(len(v)),
        "etf_rows_added": int(len(add_v)),
        "combined_verification_rows": int(len(merged_v)),
        "original_registry_rows": int(len(reg)),
        "combined_registry_rows": int(len(merged_reg)),
        "output_verification_csv": str(ov),
        "output_registry_csv": str(orp),
    }


def summarize_stock_dividend_resolution_v321(
    *,
    amount_candidates_csv: str,
    amount_audit_csv: str,
    output_json: str,
) -> dict:
    """Summarize why stock dividend cash amounts remain unresolved."""
    candidates = pd.read_csv(amount_candidates_csv, dtype=str).fillna("")
    audit = pd.read_csv(amount_audit_csv, dtype=str).fillna("")
    counts = audit["status"].value_counts().to_dict() if "status" in audit.columns else {}
    payload = {
        "phase": "V3.2.1 Phase 5.9",
        "cash_amount_candidate_rows": int(len(candidates)),
        "queue_rows_audited": int(len(audit)),
        "status_counts": {str(k): int(v) for k, v in counts.items()},
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "next_priority": (
            "Resolve actual stock ex-dates and remaining ambiguous/missing cash amounts; "
            "do not convert missing amounts to zero."
        ),
    }
    out = Path(output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload | {"output_json": str(out)}
