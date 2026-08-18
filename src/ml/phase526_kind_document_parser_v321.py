from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
from bs4 import BeautifulSoup


DATE_RE = re.compile(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})")
NUMBER_RE = re.compile(r"^-?\d[\d,]*(?:\.\d+)?$")
FILE_ID_RE = re.compile(r"(?P<acpt_no>\d{14})_(?P<doc_no>\d{14})\.html$")


def _normalize_date(value: str) -> str:
    match = DATE_RE.search(value or "")
    if not match:
        return ""
    return f"{int(match.group(1)):04d}{int(match.group(2)):02d}{int(match.group(3)):02d}"


def _normalize_number(value: str) -> str:
    cleaned = (value or "").replace(",", "").strip()
    return cleaned if NUMBER_RE.fullmatch(cleaned) else ""


def parse_kind_dividend_document(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    result = {
        "dividend_type": "",
        "dividend_kind": "",
        "common_cash_amount": "",
        "preferred_cash_amount": "",
        "total_cash_amount": "",
        "record_date": "",
        "payment_date": "",
        "board_date": "",
        "parse_status": "PARSE_FAILED",
    }
    expect_preferred_amount = False

    for tr in soup.find_all("tr"):
        cells = [
            " ".join(cell.get_text(" ", strip=True).split())
            for cell in tr.find_all(["th", "td"], recursive=False)
        ]
        if not cells:
            continue
        label = re.sub(r"\s+", "", cells[0])
        if label != "종류주식" and "3.1주당배당금" not in label:
            expect_preferred_amount = False

        if label.startswith("1.배당구분") and len(cells) >= 2:
            result["dividend_type"] = cells[-1]
        elif label.startswith("2.배당종류") and len(cells) >= 2:
            result["dividend_kind"] = cells[-1]
        elif "3.1주당배당금" in label:
            values = [_normalize_number(value) for value in cells[1:]]
            values = [value for value in values if value]
            if values:
                result["common_cash_amount"] = values[-1]
                expect_preferred_amount = True
        elif label == "종류주식" and expect_preferred_amount:
            values = [_normalize_number(value) for value in cells[1:]]
            values = [value for value in values if value]
            if values:
                result["preferred_cash_amount"] = values[-1]
            expect_preferred_amount = False
        elif label.startswith("5.배당금총액") and len(cells) >= 2:
            result["total_cash_amount"] = _normalize_number(cells[-1])
        elif label.startswith("6.배당기준일") and len(cells) >= 2:
            result["record_date"] = _normalize_date(cells[-1])
        elif label.startswith("7.배당금지급예정일자") and len(cells) >= 2:
            result["payment_date"] = _normalize_date(cells[-1])
        elif label.startswith("10.이사회결의일") and len(cells) >= 2:
            result["board_date"] = _normalize_date(cells[-1])

    if result["common_cash_amount"] and result["record_date"]:
        result["parse_status"] = "SUCCESS"
    elif any(result[key] for key in ("common_cash_amount", "record_date", "board_date")):
        result["parse_status"] = "PARTIAL"
    return result


def parse_kind_dividend_documents_v321(*, documents_dir: str, output_csv: str) -> dict:
    root = Path(documents_dir)
    if not root.exists():
        raise FileNotFoundError(str(root))

    rows = []
    for path in sorted(root.glob("*.html")):
        parsed = parse_kind_dividend_document(path.read_text(encoding="utf-8"))
        match = FILE_ID_RE.match(path.name)
        parsed.update({
            "kind_acpt_no": match.group("acpt_no") if match else "",
            "kind_doc_no": match.group("doc_no") if match else "",
            "document_path": str(path),
        })
        rows.append(parsed)

    columns = [
        "kind_acpt_no", "kind_doc_no", "dividend_type", "dividend_kind",
        "common_cash_amount", "preferred_cash_amount", "total_cash_amount",
        "record_date", "payment_date", "board_date", "parse_status",
        "document_path",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    target = Path(output_csv)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, encoding="utf-8-sig")
    return {
        "documents": int(len(frame)),
        "status_counts": frame["parse_status"].value_counts().to_dict() if not frame.empty else {},
        "output_csv": str(target),
    }
