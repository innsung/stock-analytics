from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from src.ml.phase518_kind_retry_v321 import _resolve_ids, build_kind_retry_queue_v321


def test_resolve_ids_from_explicit_columns():
    row = pd.Series({"kind_acpt_no": "20260527000541", "kind_doc_no": "20260527001263"})
    assert _resolve_ids(row) == ("20260527000541", "20260527001263")


def test_resolve_ids_from_urls():
    row = pd.Series({
        "market_source_url": "https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno=20260527000541",
        "market_reference": "docNo=20260527001263",
    })
    assert _resolve_ids(row) == ("20260527000541", "20260527001263")


def test_build_retry_queue_without_live_fetch(tmp_path: Path):
    src = tmp_path / "crosscheck.csv"
    audit = tmp_path / "audit.csv"
    retry = tmp_path / "retry.csv"
    out = tmp_path / "out.csv"

    pd.DataFrame([
        {
            "queue_event_id": "q1",
            "code": "660",
            "market_source_url": "https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno=20260527000541",
            "market_reference": "docNo=20260527001263",
            "verification_status": "UNRESOLVED",
        },
        {
            "queue_event_id": "q2",
            "code": "5930",
            "market_source_url": "",
            "market_reference": "",
            "verification_status": "UNRESOLVED",
        },
    ]).to_csv(src, index=False, encoding="utf-8-sig")

    result = build_kind_retry_queue_v321(
        crosscheck_csv=str(src),
        audit_csv=str(audit),
        retry_queue_csv=str(retry),
        output_csv=str(out),
        live_fetch=False,
    )

    assert result["input_rows"] == 2
    assert result["retry_rows"] == 0

    a = pd.read_csv(audit, dtype=str).fillna("")
    assert list(a["status"]) == ["NOT_FETCHED", "KIND_ID_UNAVAILABLE"]

    o = pd.read_csv(out, dtype=str).fillna("")
    assert "kind_fetch_status" in o.columns
    assert o.loc[0, "kind_doc_no"] == "20260527001263"


def test_main_namespace_registers_kind_retry_builder():
    import src.main as main_module

    assert main_module.build_kind_retry_queue_v321 is build_kind_retry_queue_v321


def test_successful_fetch_persists_document_with_hash(tmp_path: Path, monkeypatch):
    src = tmp_path / "crosscheck.csv"
    audit = tmp_path / "audit.csv"
    retry = tmp_path / "retry.csv"
    out = tmp_path / "out.csv"
    documents = tmp_path / "documents"
    pd.DataFrame([{
        "queue_event_id": "q1",
        "code": "660",
        "kind_acpt_no": "20260422000788",
        "kind_doc_no": "20260422002195",
    }]).to_csv(src, index=False)

    monkeypatch.setattr(
        "src.ml.phase518_kind_retry_v321.fetch_kind_print_document",
        lambda *args, **kwargs: SimpleNamespace(
            status=SimpleNamespace(value="SUCCESS"),
            status_code=200,
            retryable=False,
            final_url="https://kind.krx.co.kr/external/document.html",
            error=None,
            content="<html><body>dividend</body></html>",
        ),
    )
    result = build_kind_retry_queue_v321(
        crosscheck_csv=str(src),
        audit_csv=str(audit),
        retry_queue_csv=str(retry),
        output_csv=str(out),
        documents_dir=str(documents),
        live_fetch=True,
    )

    assert result["status_counts"] == {"SUCCESS": 1}
    saved = list(documents.glob("*.html"))
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == "<html><body>dividend</body></html>"
    row = pd.read_csv(audit, dtype=str).fillna("").iloc[0]
    assert len(row["document_sha256"]) == 64
    assert row["document_path"] == str(saved[0])
