from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "queue_event_id",
    "code",
    "event_family",
    "source_reference_date",
    "source_description",
    "resolution_status",
    "workstream",
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _mechanic(event_family: str, description: str) -> str:
    text = _norm(description)
    if event_family == "DIVIDEND_OR_DISTRIBUTION":
        return "CASH_DIVIDEND"
    if "유상증자" in text:
        return "RIGHTS_OFFERING"
    if "무상증자" in text:
        return "BONUS_ISSUE"
    if "감자" in text:
        return "CAPITAL_REDUCTION"
    if "주식분할" in text or "주식병합" in text:
        return "SHARE_SPLIT_OR_CONSOLIDATION"
    if "회사분할" in text or "분할합병" in text:
        return "SPINOFF_OR_SPLIT_MERGER"
    if "합병" in text:
        return "MERGER"
    if "주식교환" in text or "주식이전" in text:
        return "SHARE_EXCHANGE_OR_TRANSFER"
    if any(word in text for word in ("전환사채", "교환사채", "신주인수권부사채")):
        return "EQUITY_LINKED_SECURITY"
    if "타법인주식" in text or "출자증권" in text:
        return "OTHER_COMPANY_SECURITIES"
    if "상장" in text:
        return "LISTING_ADMINISTRATION"
    if "매매거래정지" in text:
        return "TRADING_ADMINISTRATION"
    return "OTHER_CORPORATE_DISCLOSURE"


def _role(event_family: str, description: str) -> str:
    text = _norm(description)
    if event_family == "DIVIDEND_OR_DISTRIBUTION":
        return "PERIODIC_REPORT_FACT"
    if "정정" in text:
        return "AMENDMENT"
    if "첨부" in text:
        return "ATTACHMENT"
    if "종료보고서" in text or "발행결과" in text or "청약결과" in text:
        return "FOLLOWUP_RESULT"
    if "매매거래정지" in text:
        return "MARKET_ADMINISTRATION"
    if "결정" in text:
        return "PRIMARY_OR_AMENDED_DECISION"
    return "OTHER_DISCLOSURE"


def _lane(event_family: str, role: str, mechanic: str) -> tuple[str, int, str]:
    if event_family == "DIVIDEND_OR_DISTRIBUTION":
        return (
            "DIVIDEND_DECISION_EXDATE_LINKAGE",
            1,
            "LINK_PERIODIC_FACT_TO_PRE_EXDATE_DECISION_AND_MARKET_EXDATE",
        )
    if role in {"AMENDMENT", "ATTACHMENT", "FOLLOWUP_RESULT"}:
        return (
            "CORPORATE_ACTION_LEGAL_EVENT_CHAIN",
            2,
            "LINK_TO_PRIMARY_DECISION_BEFORE_FACTOR_REVIEW",
        )
    adjustment_mechanics = {
        "RIGHTS_OFFERING",
        "BONUS_ISSUE",
        "CAPITAL_REDUCTION",
        "SHARE_SPLIT_OR_CONSOLIDATION",
        "SPINOFF_OR_SPLIT_MERGER",
        "MERGER",
        "SHARE_EXCHANGE_OR_TRANSFER",
    }
    if mechanic in adjustment_mechanics and role == "PRIMARY_OR_AMENDED_DECISION":
        return (
            "PRIMARY_ADJUSTMENT_DOCUMENT_REVIEW",
            3,
            "ACQUIRE_ORIGINAL_DOCUMENT_AND_VALIDATE_EFFECTIVE_MECHANICS",
        )
    return (
        "NON_ADJUSTMENT_SEMANTIC_REVIEW",
        4,
        "PROVE_NO_LISTED_SHARE_OR_CASH_ADJUSTMENT_BEFORE_EXCLUSION",
    )


def build_historical_backlog_execution_manifest_v321(
    *, actionable_queue_csv: str, output_csv: str, summary_json: str
) -> dict:
    queue = pd.read_csv(actionable_queue_csv, dtype=str).fillna("")
    missing = sorted(REQUIRED_COLUMNS - set(queue.columns))
    if missing:
        raise ValueError(f"actionable queue missing columns: {', '.join(missing)}")

    targets = queue[queue["workstream"].eq("P5_HISTORICAL_BACKLOG")].copy()
    if not targets["queue_event_id"].is_unique:
        raise ValueError("historical backlog contains duplicate queue_event_id values")
    if not targets["resolution_status"].eq("UNRESOLVED").all():
        raise ValueError("historical backlog must contain only UNRESOLVED rows")

    rows: list[dict[str, str | int]] = []
    for target in targets.itertuples(index=False):
        mechanic = _mechanic(target.event_family, target.source_description)
        role = _role(target.event_family, target.source_description)
        lane, lane_order, next_action = _lane(target.event_family, role, mechanic)
        year = str(target.source_reference_date)[:4]
        rows.append(
            {
                **target._asdict(),
                "document_role": role,
                "mechanic_family": mechanic,
                "execution_lane": lane,
                "execution_lane_order": lane_order,
                "candidate_cluster_key": f"{str(target.code).zfill(6)}:{mechanic}:{year}",
                "next_action": next_action,
                "phase582_status": "ROUTED_NOT_RESOLVED",
            }
        )

    output = pd.DataFrame(rows)
    if not output.empty:
        output = output.sort_values(
            ["execution_lane_order", "source_reference_date", "code", "queue_event_id"],
            ascending=[True, False, True, True],
        )
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")

    lane_counts = output["execution_lane"].value_counts().to_dict() if len(output) else {}
    role_counts = output["document_role"].value_counts().to_dict() if len(output) else {}
    mechanic_counts = output["mechanic_family"].value_counts().to_dict() if len(output) else {}
    summary = {
        "input_actionable_rows": int(len(queue)),
        "historical_backlog_rows": int(len(output)),
        "accounted_rows": int(sum(lane_counts.values())),
        "resolution_status_changed": False,
        "execution_lane_counts": lane_counts,
        "document_role_counts": role_counts,
        "mechanic_family_counts": mechanic_counts,
        "candidate_cluster_count": int(output["candidate_cluster_key"].nunique()) if len(output) else 0,
        "next_execution_lane": next(iter(lane_counts), ""),
        "output_csv": str(output_path),
    }
    summary_path = Path(summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
