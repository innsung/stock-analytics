import json

import pandas as pd
import pytest

from src.ml.phase582_historical_backlog_router_v321 import (
    build_historical_backlog_execution_manifest_v321,
)


def test_routes_each_historical_evidence_type_without_resolving(tmp_path):
    rows = [
        {"queue_event_id": "d1", "code": "5930", "event_family": "DIVIDEND_OR_DISTRIBUTION",
         "source_reference_date": "20240312", "source_description": "OpenDART alotMatter 2024",
         "resolution_status": "UNRESOLVED", "workstream": "P5_HISTORICAL_BACKLOG"},
        {"queue_event_id": "c1", "code": "6400", "event_family": "CORPORATE_ACTION",
         "source_reference_date": "20240229", "source_description": "[정정공시]유상증자결정",
         "resolution_status": "UNRESOLVED", "workstream": "P5_HISTORICAL_BACKLOG"},
        {"queue_event_id": "c2", "code": "660", "event_family": "CORPORATE_ACTION",
         "source_reference_date": "20240110", "source_description": "주식분할 결정",
         "resolution_status": "UNRESOLVED", "workstream": "P5_HISTORICAL_BACKLOG"},
        {"queue_event_id": "c3", "code": "35420", "event_family": "CORPORATE_ACTION",
         "source_reference_date": "20240109", "source_description": "합병등종료보고서(합병)",
         "resolution_status": "UNRESOLVED", "workstream": "P5_HISTORICAL_BACKLOG"},
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "queue.csv", index=False)

    result = build_historical_backlog_execution_manifest_v321(
        actionable_queue_csv=str(tmp_path / "queue.csv"),
        output_csv=str(tmp_path / "manifest.csv"), summary_json=str(tmp_path / "summary.json"))

    output = pd.read_csv(tmp_path / "manifest.csv", dtype=str).set_index("queue_event_id")
    assert result["historical_backlog_rows"] == result["accounted_rows"] == 4
    assert output.loc["d1", "execution_lane"] == "DIVIDEND_DECISION_EXDATE_LINKAGE"
    assert output.loc["c1", "execution_lane"] == "CORPORATE_ACTION_LEGAL_EVENT_CHAIN"
    assert output.loc["c2", "execution_lane"] == "PRIMARY_ADJUSTMENT_DOCUMENT_REVIEW"
    assert output.loc["c3", "document_role"] == "FOLLOWUP_RESULT"
    assert set(output["phase582_status"]) == {"ROUTED_NOT_RESOLVED"}
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["resolution_status_changed"] is False


def test_rejects_missing_identity_columns(tmp_path):
    pd.DataFrame([{"queue_event_id": "x"}]).to_csv(tmp_path / "queue.csv", index=False)
    with pytest.raises(ValueError, match="missing columns"):
        build_historical_backlog_execution_manifest_v321(
            actionable_queue_csv=str(tmp_path / "queue.csv"),
            output_csv=str(tmp_path / "manifest.csv"), summary_json=str(tmp_path / "summary.json"))
