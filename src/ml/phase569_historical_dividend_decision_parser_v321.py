from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd


def _plain_text(document: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", document,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _last(pattern: str, text: str) -> str:
    values = re.findall(pattern, text, flags=re.IGNORECASE)
    return values[-1].strip() if values else ""


def _money(value: str) -> str:
    cleaned = re.sub(r"[^0-9.-]", "", value.replace(",", ""))
    return cleaned if re.fullmatch(r"\d+(?:\.\d+)?", cleaned) else ""


def parse_dividend_decision_text(document: str) -> dict[str, str]:
    text = _plain_text(document)
    common = _last(r"1주당\s*배당금\s*\(원\)\s*보통주식\s*([0-9][0-9,.]*)", text)
    preferred = _last(r"1주당\s*배당금\s*\(원\).*?종류주식\s*([0-9][0-9,.]*)", text)
    record = _last(r"배당기준일\s*([0-9]{4}[-./][0-9]{2}[-./][0-9]{2})", text)
    payment = _last(r"배당금지급\s*예정일자\s*([0-9]{4}[-./][0-9]{2}[-./][0-9]{2})", text)
    decision = _last(r"이사회결의일\s*\(결정일\)\s*([0-9]{4}[-./][0-9]{2}[-./][0-9]{2})", text)
    normalize = lambda value: value.replace(".", "-").replace("/", "-")
    return {
        "common_cash_dividend_per_share": _money(common),
        "preferred_cash_dividend_per_share": _money(preferred),
        "dividend_record_date": normalize(record),
        "payment_scheduled_date": normalize(payment),
        "board_decision_date": normalize(decision),
    }


def parse_historical_dividend_decisions_v321(*, acquisition_csv: str, output_csv: str) -> dict:
    manifest = pd.read_csv(acquisition_csv, dtype=str).fillna("")
    rows: list[dict[str, str]] = []
    for item in manifest.itertuples(index=False):
        base = item._asdict()
        parsed = {"common_cash_dividend_per_share": "", "preferred_cash_dividend_per_share": "",
                  "dividend_record_date": "", "payment_scheduled_date": "", "board_decision_date": ""}
        errors: list[str] = []
        for path_text in str(item.document_paths).split("|"):
            if not path_text:
                continue
            try:
                candidate = parse_dividend_decision_text(Path(path_text).read_text(encoding="utf-8"))
                for key, value in candidate.items():
                    if value:
                        parsed[key] = value
            except (OSError, UnicodeError) as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        complete = bool(parsed["common_cash_dividend_per_share"] and
                        parsed["dividend_record_date"] and parsed["board_decision_date"])
        rows.append({**base, **parsed,
                     "parse_status": "PARSED_DECISION_TERMS" if complete else "INCOMPLETE_DECISION_TERMS",
                     "strict_promotion_status": "NOT_PROMOTED_RECORD_DATE_IS_NOT_EX_DATE" if complete else "NOT_PROMOTED_INCOMPLETE_TERMS",
                     "parse_error": " | ".join(errors)})
    output = pd.DataFrame(rows)
    path = Path(output_csv); path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(path, index=False, encoding="utf-8-sig")
    return {"manifest_rows": len(output),
            "parsed_rows": int(output["parse_status"].eq("PARSED_DECISION_TERMS").sum()),
            "incomplete_rows": int(output["parse_status"].eq("INCOMPLETE_DECISION_TERMS").sum()),
            "output_csv": str(path)}
