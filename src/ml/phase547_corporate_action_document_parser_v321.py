from __future__ import annotations

from pathlib import Path
import re
import warnings

import pandas as pd
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH


DATE_RE = re.compile(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})")
NUMBER_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)")


def _date(text: str) -> str:
    match = DATE_RE.search(text or "")
    return (f"{int(match.group(1)):04d}{int(match.group(2)):02d}{int(match.group(3)):02d}"
            if match else "")


def _number_after(text: str, label: str) -> str:
    tail = text.split(label, 1)[-1]
    match = NUMBER_RE.search(tail)
    return match.group(1) if match else ""


def parse_corporate_action_documents_v321(
    *, acquisition_csv: str, output_csv: str,
) -> dict:
    acquisition = pd.read_csv(acquisition_csv, dtype=str).fillna("")
    rows = []
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    for _, item in acquisition.iterrows():
        texts = []
        for value in item["document_paths"].split("|"):
            if value:
                soup = BeautifulSoup(Path(value).read_text(encoding="utf-8"), "html.parser")
                texts.extend(" ".join(tr.get_text(" ", strip=True).split()) for tr in soup.find_all("tr"))
        joined = "\n".join(texts)
        allotment = next((_date(x) for x in texts if "신주배정기준일" in x and _date(x)), "")
        listing = next((_date(x) for x in texts if ("신주의 상장 예정일" in x or "신주상장예정일" in x) and _date(x)), "")
        reduction_date = next((_date(x) for x in texts if "감자기준일" in x and _date(x)), "")
        allotment_ratio = next((_number_after(x, "1주당 신주배정주식수 (주)") for x in texts
                                if "1주당 신주배정주식수 (주)" in x), "")
        reduction_ratio = next((_number_after(x, "보통주식 (%)") for x in texts
                                if "감자비율" in x and "보통주식 (%)" in x), "")
        event_date = allotment or reduction_date or listing
        known_at = item["source_reference_date"]
        if not event_date:
            eligibility = "MISSING_OFFICIAL_EFFECTIVE_DATE"
        elif event_date > RESEARCH_SEEN_THROUGH:
            eligibility = "EVENT_AFTER_RESEARCH_CUTOFF"
        elif known_at > event_date:
            eligibility = "KNOWN_AT_AFTER_EVENT_DATE"
        elif item["action_type_hint"] == "REVERSE_SPLIT" and reduction_ratio and float(reduction_ratio) < 1:
            eligibility = "MINOR_CAPITAL_REDUCTION_NEEDS_SEMANTIC_REVIEW"
        elif item["action_type_hint"] == "RIGHTS" and not allotment:
            eligibility = "NO_SHAREHOLDER_ALLOTMENT_DATE"
        else:
            eligibility = "READY_FOR_KRX_MARKET_ADJUSTMENT_CHECK"
        rows.append({
            "queue_event_id": item["queue_event_id"], "code": str(item["code"]).zfill(6),
            "rcept_no": item["rcept_no"], "known_at": known_at,
            "action_type_hint": item["action_type_hint"], "allotment_record_date": allotment,
            "new_share_listing_date": listing, "capital_reduction_date": reduction_date,
            "allotment_ratio": allotment_ratio, "capital_reduction_percent": reduction_ratio,
            "official_event_date_candidate": event_date, "market_check_eligibility": eligibility,
            "promotion_status": "PARSED_OFFICIAL_DOCUMENT_NOT_STRICT_EVIDENCE",
        })
    output = pd.DataFrame(rows)
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target, index=False, encoding="utf-8-sig")
    return {"input_rows": len(acquisition), "parsed_rows": len(output),
            "eligibility_counts": output["market_check_eligibility"].value_counts().to_dict(),
            "output_csv": str(target)}
