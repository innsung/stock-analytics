from __future__ import annotations

from pathlib import Path
from typing import Iterable
import hashlib
import re

import pandas as pd

from src.kind_service import fetch_kind_external_document, fetch_kind_print_document


ACPTNO_RE = re.compile(r"(?:acptno|acptNo|acpt_no)[=:/\s]+(\d{14})", re.I)
DOCNO_RE = re.compile(r"(?:docNo|docno|doc_no)[=:/\s]+(\d{14})", re.I)


def _first_nonempty(row: pd.Series, names: Iterable[str]) -> str:
    for name in names:
        if name in row.index:
            value = str(row.get(name, "") or "").strip()
            if value and value.lower() != "nan":
                return value
    return ""


def _extract_id(text: str, pattern: re.Pattern[str]) -> str:
    if not text:
        return ""
    m = pattern.search(str(text))
    return m.group(1) if m else ""


def _resolve_ids(row: pd.Series) -> tuple[str, str]:
    acpt_no = _first_nonempty(
        row,
        ("kind_acpt_no", "kind_acptno", "acpt_no", "acptno", "acptNo"),
    )
    doc_no = _first_nonempty(
        row,
        ("kind_doc_no", "kind_docno", "doc_no", "docno", "docNo"),
    )

    scan_text = " ".join(
        _first_nonempty(row, (name,))
        for name in (
            "market_reference",
            "market_source_url",
            "kind_url",
            "source_url",
            "verification_reference",
            "official_document_reference",
            "market_note",
        )
    )

    if not acpt_no:
        acpt_no = _extract_id(scan_text, ACPTNO_RE)
    if not doc_no:
        doc_no = _extract_id(scan_text, DOCNO_RE)

    return acpt_no, doc_no


def _resolve_document_url(row: pd.Series) -> str:
    return _first_nonempty(
        row,
        ("kind_document_url", "document_url", "kind_external_url"),
    )


def build_kind_retry_queue_v321(
    *,
    crosscheck_csv: str,
    audit_csv: str,
    retry_queue_csv: str,
    output_csv: str | None = None,
    documents_dir: str | None = None,
    timeout: int = 30,
    live_fetch: bool = True,
) -> dict:
    src = Path(crosscheck_csv)
    if not src.exists():
        raise FileNotFoundError(str(src))

    df = pd.read_csv(src, dtype=str).fillna("")
    audit_rows: list[dict] = []
    enriched = df.copy()

    extra_columns = [
        "kind_fetch_status",
        "kind_retryable",
        "kind_http_status",
        "kind_final_url",
        "kind_fetch_error",
        "kind_acpt_no",
        "kind_doc_no",
        "kind_document_path",
        "kind_document_sha256",
        "kind_document_bytes",
    ]
    for col in extra_columns:
        if col not in enriched.columns:
            enriched[col] = ""

    for idx, row in df.iterrows():
        acpt_no, doc_no = _resolve_ids(row)
        document_url = _resolve_document_url(row)

        base_audit = {
            "row_index": int(idx),
            "queue_event_id": str(row.get("queue_event_id", "") or ""),
            "code": str(row.get("code", "") or "").zfill(6)
            if str(row.get("code", "") or "").strip()
            else "",
            "kind_acpt_no": acpt_no,
            "kind_doc_no": doc_no,
            "status": "",
            "retryable": False,
            "http_status": "",
            "final_url": "",
            "document_path": "",
            "document_sha256": "",
            "document_bytes": "",
            "error": "",
        }

        if not doc_no:
            base_audit.update(
                status="KIND_ID_UNAVAILABLE",
                retryable=False,
                error="No KIND docNo found in Phase 5.16 row",
            )
            audit_rows.append(base_audit)
            enriched.at[idx, "kind_fetch_status"] = "KIND_ID_UNAVAILABLE"
            enriched.at[idx, "kind_retryable"] = "False"
            enriched.at[idx, "kind_acpt_no"] = acpt_no
            enriched.at[idx, "kind_doc_no"] = doc_no
            continue

        if not live_fetch:
            base_audit.update(status="NOT_FETCHED", retryable=False)
            audit_rows.append(base_audit)
            enriched.at[idx, "kind_fetch_status"] = "NOT_FETCHED"
            enriched.at[idx, "kind_retryable"] = "False"
            enriched.at[idx, "kind_acpt_no"] = acpt_no
            enriched.at[idx, "kind_doc_no"] = doc_no
            continue

        if document_url:
            result = fetch_kind_external_document(document_url, timeout=timeout)
        else:
            result = fetch_kind_print_document(
                doc_no,
                acpt_no=acpt_no or None,
                timeout=timeout,
            )

        status = result.status.value
        http_status = "" if result.status_code is None else str(result.status_code)
        document_path = ""
        document_sha256 = ""
        document_bytes = ""
        if status == "SUCCESS" and documents_dir is not None:
            content_bytes = result.content.encode("utf-8")
            document_sha256 = hashlib.sha256(content_bytes).hexdigest()
            document_bytes = str(len(content_bytes))
            target_dir = Path(documents_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{acpt_no or 'no-acpt'}_{doc_no}.html"
            target.write_bytes(content_bytes)
            document_path = str(target)

        base_audit.update(
            status=status,
            retryable=bool(result.retryable),
            http_status=http_status,
            final_url=result.final_url,
            document_path=document_path,
            document_sha256=document_sha256,
            document_bytes=document_bytes,
            error=result.error or "",
        )
        audit_rows.append(base_audit)

        enriched.at[idx, "kind_fetch_status"] = status
        enriched.at[idx, "kind_retryable"] = str(bool(result.retryable))
        enriched.at[idx, "kind_http_status"] = http_status
        enriched.at[idx, "kind_final_url"] = result.final_url
        enriched.at[idx, "kind_fetch_error"] = result.error or ""
        enriched.at[idx, "kind_acpt_no"] = acpt_no
        enriched.at[idx, "kind_doc_no"] = doc_no
        enriched.at[idx, "kind_document_path"] = document_path
        enriched.at[idx, "kind_document_sha256"] = document_sha256
        enriched.at[idx, "kind_document_bytes"] = document_bytes

    audit = pd.DataFrame(
        audit_rows,
        columns=[
            "row_index",
            "queue_event_id",
            "code",
            "kind_acpt_no",
            "kind_doc_no",
            "status",
            "retryable",
            "http_status",
            "final_url",
            "document_path",
            "document_sha256",
            "document_bytes",
            "error",
        ],
    )

    retry = audit[audit["retryable"].astype(bool)].copy() if not audit.empty else audit.copy()

    audit_path = Path(audit_csv)
    retry_path = Path(retry_queue_csv)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    retry_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    retry.to_csv(retry_path, index=False, encoding="utf-8-sig")

    output_path = None
    if output_csv:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        enriched.to_csv(output_path, index=False, encoding="utf-8-sig")

    status_counts = (
        {str(k): int(v) for k, v in audit["status"].value_counts().to_dict().items()}
        if not audit.empty
        else {}
    )

    return {
        "phase": "V3.2.1 Phase 5.18",
        "input_rows": int(len(df)),
        "audit_rows": int(len(audit)),
        "retry_rows": int(len(retry)),
        "status_counts": status_counts,
        "audit_csv": str(audit_path),
        "retry_queue_csv": str(retry_path),
        "output_csv": str(output_path) if output_path else "",
        "documents_dir": str(documents_dir or ""),
    }
