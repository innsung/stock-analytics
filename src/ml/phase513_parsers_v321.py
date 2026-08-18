from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import hashlib
import json
import re
import time

import pandas as pd
import requests

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

DATE_KEYS = ("date","dt","day","일자","일","기준일","지급일","분배락","배당락","ex")
AMOUNT_KEYS = ("amount","amt","cash","dividend","distribution","분배금","배당금","금액","원")
RECORD_LABELS = ("배당기준일","현금배당기준일","배당 기준일","기준일")
EX_LABELS = ("배당락일","분배락일","권리락일")
DATE_RE = re.compile(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})")


def _clean_date(value: str) -> str:
    s = re.sub(r"[^0-9]", "", str(value or ""))
    if len(s) != 8:
        return ""
    try:
        pd.to_datetime(s, format="%Y%m%d")
    except Exception:
        return ""
    return s


def _flatten_json(obj, path="$"):
    if isinstance(obj, dict):
        for k,v in obj.items():
            yield from _flatten_json(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i,v in enumerate(obj):
            yield from _flatten_json(v, f"{path}[{i}]")
    else:
        yield path, obj


def inspect_kodex_probe_responses_v321(
    *,
    probe_csv: str,
    output_dir: str,
    min_response_keyword_score: int = 2,
    timeout_seconds: float = 15.0,
    product_host: str = "m.samsungfund.com",
) -> dict:
    """Re-fetch high-signal official endpoints and inspect response structure.

    Bodies are persisted for audit. Date/amount-like fields are candidates only and
    are never promoted directly into ETF distribution evidence.
    """
    p=Path(probe_csv)
    if not p.exists():
        raise FileNotFoundError(f"KODEX probe CSV가 없습니다: {p}")
    f=pd.read_csv(p,dtype=str).fillna("")
    required={"url","probe_status","response_keyword_score"}
    missing=required-set(f.columns)
    if missing:
        raise ValueError("probe CSV 누락 열: "+", ".join(sorted(missing)))
    f["score"]=pd.to_numeric(f["response_keyword_score"],errors="coerce").fillna(0)
    selected=f[(f["probe_status"]=="OK") & (f["score"]>=int(min_response_keyword_score))].copy()

    target=Path(output_dir)
    bodies=target/"bodies"
    target.mkdir(parents=True,exist_ok=True)
    bodies.mkdir(parents=True,exist_ok=True)
    sess=requests.Session()
    headers={"User-Agent":"Mozilla/5.0"}
    rows=[]
    field_rows=[]
    for _,r in selected.iterrows():
        url=r["url"]
        parsed=urlparse(url)
        status="SKIPPED_UNSAFE_ORIGIN"
        http_status=""
        content_type=""
        body_file=""
        error=""
        date_fields=0
        amount_fields=0
        if parsed.scheme in {"http","https"} and parsed.netloc==product_host:
            try:
                resp=sess.get(url,timeout=timeout_seconds,headers=headers,allow_redirects=True)
                http_status=str(resp.status_code)
                content_type=resp.headers.get("content-type","")
                ext=".json" if "json" in content_type.lower() else ".html"
                name=hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]+ext
                bp=bodies/name
                bp.write_bytes(resp.content)
                body_file=str(bp)
                status="OK" if resp.ok else "HTTP_ERROR"

                text=resp.text
                if "json" in content_type.lower() or text.lstrip().startswith(("{","[")):
                    try:
                        payload=resp.json()
                        for path,val in _flatten_json(payload):
                            low=path.lower()
                            date_like=any(k.lower() in low for k in DATE_KEYS)
                            amount_like=any(k.lower() in low for k in AMOUNT_KEYS)
                            value=str(val)
                            normalized_date=_clean_date(value)
                            numeric=""
                            if amount_like:
                                try:
                                    numeric=float(str(val).replace(",",""))
                                except Exception:
                                    numeric=""
                            if date_like or amount_like:
                                field_rows.append({
                                    "url":url,"path":path,"value":value[:500],
                                    "date_like":date_like,"normalized_date":normalized_date,
                                    "amount_like":amount_like,"numeric_amount":numeric,
                                })
                                date_fields += int(bool(date_like and normalized_date))
                                amount_fields += int(bool(amount_like and numeric!=""))
                    except Exception:
                        pass
                else:
                    # HTML/text fallback: only count explicit distribution context.
                    compact=re.sub(r"\s+"," ",text)
                    for m in DATE_RE.finditer(compact):
                        ctx=compact[max(0,m.start()-100):min(len(compact),m.end()+140)]
                        if "분배금" in ctx or "배당" in ctx:
                            date=f"{int(m.group(1)):04d}{int(m.group(2)):02d}{int(m.group(3)):02d}"
                            field_rows.append({
                                "url":url,"path":"HTML_CONTEXT","value":ctx[:500],
                                "date_like":True,"normalized_date":date,
                                "amount_like":False,"numeric_amount":"",
                            })
                            date_fields+=1
            except Exception as exc:
                status="FAILED"
                error=f"{type(exc).__name__}: {exc}"
        rows.append({
            "url":url,"status":status,"http_status":http_status,
            "content_type":content_type,"body_file":body_file,
            "date_fields":date_fields,"amount_fields":amount_fields,
            "error":error,"promotion_status":"STRUCTURE_INSPECTION_ONLY",
        })
        time.sleep(.05)

    audit=pd.DataFrame(rows)
    fields=pd.DataFrame(field_rows)
    audit_csv=target/"kodex_high_signal_response_audit.csv"
    fields_csv=target/"kodex_high_signal_field_candidates.csv"
    audit.to_csv(audit_csv,index=False,encoding="utf-8-sig")
    fields.to_csv(fields_csv,index=False,encoding="utf-8-sig")
    result={
        "selected_endpoints":int(len(selected)),
        "successful_responses":int((audit["status"]=="OK").sum()) if not audit.empty else 0,
        "responses_with_date_fields":int((audit["date_fields"]>0).sum()) if not audit.empty else 0,
        "responses_with_amount_fields":int((audit["amount_fields"]>0).sum()) if not audit.empty else 0,
        "field_candidates":int(len(fields)),
        "audit_csv":str(audit_csv),
        "fields_csv":str(fields_csv),
    }
    mp=target/"kodex_high_signal_response_manifest.json"
    mp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    result["manifest"]=str(mp)
    return result


def _strip_markup(text: str) -> str:
    text=re.sub(r"<[^>]+>"," ",text)
    text=re.sub(r"&[a-zA-Z#0-9]+;"," ",text)
    return re.sub(r"\s+"," ",text)


def extract_dart_dividend_record_dates_v321(
    dart_client,
    *,
    decision_disclosures_csv: str,
    output_csv: str,
    audit_csv: str,
    sleep_seconds: float = .05,
) -> dict:
    """Download DART filing originals and extract record/ex-date candidates.

    A unique explicit date next to an exact label is emitted as a candidate. Receipt
    date remains known_at; candidate date is not yet automatically converted to an
    exchange ex-date.
    """
    p=Path(decision_disclosures_csv)
    if not p.exists():
        raise FileNotFoundError(f"배당결정 공시 CSV가 없습니다: {p}")
    d=pd.read_csv(p,dtype=str).fillna("")
    required={"code","known_at","report_nm","rcept_no","verification_source"}
    missing=required-set(d.columns)
    if missing:
        raise ValueError("배당결정 공시 CSV 누락 열: "+", ".join(sorted(missing)))

    rows=[]
    audits=[]
    for i,r in d.iterrows():
        rcept_no=r["rcept_no"]
        code=str(r["code"]).zfill(6)
        known_at=_clean_date(r["known_at"])
        status="NO_LABEL_DATE"
        dates=[]
        error=""
        part_names=[]
        try:
            parts=dart_client.document_texts(rcept_no)
            part_names=[x["name"] for x in parts]
            for part in parts:
                text=_strip_markup(part["text"])
                for label_type,labels in (("RECORD_DATE",RECORD_LABELS),("EX_DATE",EX_LABELS)):
                    for label in labels:
                        for m in re.finditer(re.escape(label),text):
                            ctx=text[m.start():m.start()+180]
                            dm=DATE_RE.search(ctx)
                            if dm:
                                date=f"{int(dm.group(1)):04d}{int(dm.group(2)):02d}{int(dm.group(3)):02d}"
                                if date<=RESEARCH_SEEN_THROUGH:
                                    dates.append((label_type,date,label,part["name"],ctx[:300]))
            unique={(t,dte) for t,dte,_,_,_ in dates}
            if len(unique)==1:
                t,dte=next(iter(unique))
                chosen=next(x for x in dates if x[0]==t and x[1]==dte)
                rows.append({
                    "code":code,
                    "known_at":known_at,
                    "report_nm":r["report_nm"],
                    "rcept_no":rcept_no,
                    "date_role":t,
                    "candidate_date":dte,
                    "label":chosen[2],
                    "document_part":chosen[3],
                    "context":chosen[4],
                    "verification_source":"OPENDART_DOCUMENT_ORIGINAL",
                    "verification_reference":rcept_no,
                    "promotion_status":"OFFICIAL_DOCUMENT_DATE_CANDIDATE",
                })
                status="UNIQUE_OFFICIAL_DATE_CANDIDATE"
            elif len(unique)>1:
                status=f"AMBIGUOUS_OFFICIAL_DATES:{len(unique)}"
        except Exception as exc:
            status="FAILED"
            error=f"{type(exc).__name__}: {exc}"
        audits.append({
            "code":code,"rcept_no":rcept_no,"known_at":known_at,
            "status":status,"raw_date_hits":len(dates),
            "document_parts":len(part_names),"error":error,
        })
        if sleep_seconds>0:
            time.sleep(sleep_seconds)

    out=pd.DataFrame(rows)
    audit=pd.DataFrame(audits)
    op=Path(output_csv); ap=Path(audit_csv)
    op.parent.mkdir(parents=True,exist_ok=True)
    ap.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(op,index=False,encoding="utf-8-sig")
    audit.to_csv(ap,index=False,encoding="utf-8-sig")
    counts=audit["status"].value_counts().to_dict() if not audit.empty else {}
    return {
        "disclosures":int(len(d)),
        "date_candidates":int(len(out)),
        "status_counts":{str(k):int(v) for k,v in counts.items()},
        "output_csv":str(op),
        "audit_csv":str(ap),
    }


def merge_dividend_amount_and_record_candidates_v321(
    *,
    exdate_queue_csv: str,
    dart_record_candidates_csv: str,
    output_csv: str,
    match_days: int = 430,
) -> dict:
    """Attach unique official DART record/ex-date candidates to amount queue.

    `RECORD_DATE` remains a record date candidate; it is not silently converted into
    the prior trading day's ex-date.
    """
    q=pd.read_csv(exdate_queue_csv,dtype=str).fillna("")
    r=pd.read_csv(dart_record_candidates_csv,dtype=str).fillna("")
    required_q={"queue_event_id","code","source_reference_date","candidate_cash_amount","decision_rcept_no"}
    missing=required_q-set(q.columns)
    if missing:
        raise ValueError("exdate queue 누락 열: "+", ".join(sorted(missing)))
    required_r={"code","rcept_no","date_role","candidate_date","known_at","verification_source","verification_reference"}
    missing=required_r-set(r.columns)
    if missing:
        raise ValueError("record candidate 누락 열: "+", ".join(sorted(missing)))

    rows=[]
    for _,row in q.iterrows():
        code=str(row["code"]).zfill(6)
        rcept=row.get("decision_rcept_no","")
        cand=r[(r["code"].astype(str).str.zfill(6)==code)].copy()
        if rcept:
            exact=cand[cand["rcept_no"].eq(rcept)]
            if not exact.empty:
                cand=exact
        status="NO_OFFICIAL_DATE_CANDIDATE"
        role=""; date=""; known=""; source=""; ref=""
        if len(cand)==1:
            c=cand.iloc[0]
            status="UNIQUE_OFFICIAL_DATE_CANDIDATE"
            role=c["date_role"]; date=c["candidate_date"]; known=c["known_at"]
            source=c["verification_source"]; ref=c["verification_reference"]
        elif len(cand)>1:
            status=f"AMBIGUOUS_OFFICIAL_DATE_CANDIDATES:{len(cand)}"
        merged=row.to_dict()
        merged.update({
            "official_date_match_status":status,
            "official_date_role":role,
            "official_date_candidate":date,
            "official_date_known_at":known,
            "official_date_source":source,
            "official_date_reference":ref,
            "effective_date":"",
            "resolution_status":"UNRESOLVED",
            "next_required_evidence":(
                "EX_DATE_CONFIRMED" if role=="EX_DATE"
                else "KRX_TRADING_CALENDAR_RECORD_TO_EXDATE_MAPPING" if role=="RECORD_DATE"
                else "OFFICIAL_DATE_RESOLUTION"
            ),
        })
        rows.append(merged)
    out=pd.DataFrame(rows)
    op=Path(output_csv); op.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(op,index=False,encoding="utf-8-sig")
    counts=out["official_date_match_status"].value_counts().to_dict() if not out.empty else {}
    return {
        "rows":int(len(out)),
        "status_counts":{str(k):int(v) for k,v in counts.items()},
        "output_csv":str(op),
    }
