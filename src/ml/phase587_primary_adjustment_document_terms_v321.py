from __future__ import annotations

import html
import json
import re
import warnings
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


DATE_RE = re.compile(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})")
NUMBER_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)")
MECHANIC_TERMS = {
    "RIGHTS_OFFERING": ("유상증자",), "CAPITAL_REDUCTION": ("감자",),
    "MERGER": ("합병",), "SPINOFF_OR_SPLIT_MERGER": ("분할",),
    "SHARE_EXCHANGE_OR_TRANSFER": ("주식교환", "주식이전"),
    "SHARE_SPLIT_OR_CONSOLIDATION": ("주식분할", "주식병합"),
}
DATE_LABELS = {
    "RIGHTS_OFFERING": ("신주배정기준일", "신주의상장예정일", "신주상장예정일"),
    "CAPITAL_REDUCTION": ("감자기준일",),
    "MERGER": ("합병기일",),
    "SPINOFF_OR_SPLIT_MERGER": ("분할기일", "분할합병기일"),
    "SHARE_EXCHANGE_OR_TRANSFER": ("주식교환일", "주식이전일"),
    "SHARE_SPLIT_OR_CONSOLIDATION": ("효력발생일", "신주권상장예정일"),
}
RATIO_LABELS = {
    "RIGHTS_OFFERING": ("1주당신주배정주식수",), "CAPITAL_REDUCTION": ("감자비율",),
    "MERGER": ("합병비율",), "SPINOFF_OR_SPLIT_MERGER": ("분할비율",),
    "SHARE_EXCHANGE_OR_TRANSFER": ("교환비율", "이전비율"),
    "SHARE_SPLIT_OR_CONSOLIDATION": ("분할비율", "병합비율"),
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _date(value: str) -> str:
    match = DATE_RE.search(value)
    return f"{int(match.group(1)):04d}{int(match.group(2)):02d}{int(match.group(3)):02d}" if match else ""


def _document_rows(parts: list[dict[str, str]]) -> tuple[str, list[str]]:
    raw = " ".join(str(part.get("text", "")) for part in parts)
    rows = []
    for part in parts:
        soup = BeautifulSoup(str(part.get("text", "")), "html.parser")
        rows.extend(" ".join(tr.get_text(" ", strip=True).split()) for tr in soup.find_all("tr"))
    plain = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    return plain, rows or [plain]


def _extract(rows: list[str], labels: tuple[str, ...], *, date: bool) -> str:
    for row in rows:
        compact = _norm(row)
        for label in labels:
            if label in compact:
                tail = compact.split(label, 1)[-1]
                if date:
                    value = _date(tail)
                else:
                    match = NUMBER_RE.search(tail.replace(",", ""))
                    value = match.group(1) if match else ""
                if value:
                    return value
    return ""


def _fetch(dart_client, receipt: str, root: Path) -> tuple[list[dict[str, str]], str, str]:
    existing = sorted(root.glob(f"{receipt}_*"))
    if existing:
        try:
            return ([{"name": p.name, "text": p.read_text(encoding="utf-8")} for p in existing], "REUSED", "")
        except (OSError, UnicodeError):
            pass
    try:
        parts = dart_client.document_texts(receipt)
        for index, part in enumerate(parts):
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(part.get("name", "document.xml")))
            (root / f"{receipt}_{index:02d}_{safe}").write_text(str(part.get("text", "")), encoding="utf-8")
        return parts, "ACQUIRED" if parts else "EMPTY_DOCUMENT", ""
    except Exception as exc:
        return [], "FAILED", f"{type(exc).__name__}: {exc}"


def extract_primary_adjustment_document_terms_v321(
    dart_client, *, execution_manifest_csv: str, disclosures_csv: str,
    legal_groups_csv: str, documents_dir: str, output_csv: str,
    review_queue_csv: str, summary_json: str,
) -> dict:
    manifest = pd.read_csv(execution_manifest_csv, dtype=str).fillna("")
    disclosures = pd.read_csv(disclosures_csv, dtype=str).fillna("")
    groups = pd.read_csv(legal_groups_csv, dtype=str).fillna("")
    targets = manifest[manifest["execution_lane"].eq("PRIMARY_ADJUSTMENT_DOCUMENT_REVIEW")].copy()
    targets["code"] = targets["code"].astype(str).str.zfill(6)
    disclosures["code"] = disclosures["code"].astype(str).str.zfill(6)
    disclosures["_title"] = disclosures["report_nm"].map(_norm)
    disclosures = disclosures.drop_duplicates(["code", "rcept_dt", "_title", "rcept_no"])
    group_map = groups.drop_duplicates("parent_queue_event_id").set_index("parent_queue_event_id")
    root = Path(documents_dir); root.mkdir(parents=True, exist_ok=True)
    cache = {}
    rows, reviews = [], []
    for target in targets.itertuples(index=False):
        matches = disclosures[
            disclosures["code"].eq(target.code)
            & disclosures["rcept_dt"].eq(target.source_reference_date)
            & disclosures["_title"].eq(_norm(target.source_description))]
        candidates = sorted(set(matches["rcept_no"]) - {""})
        selection_source = ""
        if target.queue_event_id in group_map.index:
            group = group_map.loc[target.queue_event_id]
            primary_receipt = group["parent_rcept_no"]
            controlling_receipt = group["controlling_mechanics_rcept_no"]
            selection_source = "PHASE586_LEGAL_EVENT_GROUP"
        elif len(candidates) == 1:
            primary_receipt = controlling_receipt = candidates[0]
            selection_source = "UNIQUE_EXACT_DISCLOSURE_MATCH"
        else:
            primary_receipt = controlling_receipt = ""
        if controlling_receipt:
            if controlling_receipt not in cache:
                cache[controlling_receipt] = _fetch(dart_client, controlling_receipt, root)
            parts, document_status, error = cache[controlling_receipt]
        else:
            parts, document_status, error = [], "RECEIPT_AMBIGUOUS_OR_MISSING", ""
        plain, document_rows = _document_rows(parts)
        mechanic = target.mechanic_family
        mechanic_confirmed = any(term in plain for term in MECHANIC_TERMS.get(mechanic, ()))
        effective_date = _extract(document_rows, DATE_LABELS.get(mechanic, ()), date=True)
        ratio = _extract(document_rows, RATIO_LABELS.get(mechanic, ()), date=False)
        if document_status in {"ACQUIRED", "REUSED"} and mechanic_confirmed and effective_date:
            extraction_status = "TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION"
        elif document_status in {"ACQUIRED", "REUSED"} and mechanic_confirmed:
            extraction_status = "MECHANIC_CONFIRMED_EFFECTIVE_TERMS_INCOMPLETE"
        elif not controlling_receipt:
            extraction_status = "RECEIPT_SELECTION_REVIEW_REQUIRED"
        else:
            extraction_status = "DOCUMENT_OR_SEMANTIC_REVIEW_REQUIRED"
        row = {
            "queue_event_id": target.queue_event_id, "code": target.code,
            "source_reference_date": target.source_reference_date, "mechanic_family": mechanic,
            "candidate_rcept_nos": "|".join(candidates), "primary_rcept_no": primary_receipt,
            "controlling_mechanics_rcept_no": controlling_receipt, "receipt_selection_source": selection_source,
            "document_status": document_status, "mechanic_confirmed": mechanic_confirmed,
            "official_effective_date_candidate": effective_date, "ratio_or_allotment_candidate": ratio,
            "extraction_status": extraction_status, "error": error,
            "promotion_status": "NOT_PROMOTED_REQUIRES_OFFICIAL_MARKET_EFFECTIVE_DATE_AND_FACTOR_VALIDATION",
        }
        rows.append(row)
        if extraction_status != "TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION": reviews.append(row)
    output, review = pd.DataFrame(rows), pd.DataFrame(reviews)
    op, rp = Path(output_csv), Path(review_queue_csv)
    output.to_csv(op, index=False, encoding="utf-8-sig"); review.to_csv(rp, index=False, encoding="utf-8-sig")
    summary = {
        "target_rows": int(len(targets)), "selected_receipt_rows": int(output["controlling_mechanics_rcept_no"].ne("").sum()),
        "unique_documents_processed": int(len(cache)),
        "terms_extracted_rows": int(output["extraction_status"].eq("TERMS_EXTRACTED_REQUIRES_MARKET_VALIDATION").sum()),
        "review_rows": int(len(review)), "resolution_status_changed": False,
        "documents_dir": str(root), "output_csv": str(op), "review_queue_csv": str(rp),
    }
    sp = Path(summary_json); sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(sp)}
