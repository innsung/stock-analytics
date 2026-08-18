from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import json
import re
import time

import pandas as pd
import requests

from src.ml.data_integrity_v321 import RESEARCH_SEEN_THROUGH

SAFE_SCHEMES={"http","https"}
DIVIDEND_REPORT_KEYWORDS=(
    "현금ㆍ현물배당 결정","현금·현물배당 결정","현금 현물배당 결정",
    "배당기준일","배당 결정","배당결정",
)


def rank_and_probe_kodex_endpoints_v321(
    *,
    candidate_csv:str,
    output_csv:str,
    top_n:int=25,
    timeout_seconds:float=12.0,
    product_host:str="m.samsungfund.com",
) -> dict:
    p=Path(candidate_csv)
    if not p.exists():
        raise FileNotFoundError(f"KODEX endpoint candidate CSV가 없습니다: {p}")
    f=pd.read_csv(p,dtype=str).fillna("")
    required={"url","score","hits","context"}
    missing=required-set(f.columns)
    if missing:
        raise ValueError("endpoint candidate CSV 누락 열: "+", ".join(sorted(missing)))
    f["score_num"]=pd.to_numeric(f["score"],errors="coerce").fillna(0)
    f["hits_num"]=pd.to_numeric(f["hits"],errors="coerce").fillna(0)
    keywords=("분배금","distribution","dividend","payment","pay","dist","api","ajax","etf")
    f["semantic_bonus"]=f["context"].str.lower().map(
        lambda s: sum(1 for k in keywords if k.lower() in s)
    )
    f["rank_score"]=f["score_num"]*10+f["hits_num"]+f["semantic_bonus"]*3
    top=f.sort_values(["rank_score","score_num","hits_num"],ascending=False).head(int(top_n)).copy()

    sess=requests.Session()
    headers={"User-Agent":"Mozilla/5.0"}
    rows=[]
    for _,r in top.iterrows():
        url=r["url"]
        parsed=urlparse(url)
        status="SKIPPED"
        http_status=""
        content_type=""
        bytes_len=0
        response_score=0
        error=""
        if parsed.scheme in SAFE_SCHEMES and parsed.netloc==product_host:
            try:
                resp=sess.get(url,timeout=timeout_seconds,headers=headers,allow_redirects=True)
                http_status=resp.status_code
                content_type=resp.headers.get("content-type","")
                text=resp.text[:200000]
                bytes_len=len(resp.content)
                low=text.lower()
                response_score=sum(1 for k in keywords if k.lower() in low)
                status="OK" if resp.ok else "HTTP_ERROR"
            except Exception as exc:
                status="FAILED"
                error=f"{type(exc).__name__}: {exc}"
        else:
            status="SKIPPED_UNSAFE_ORIGIN"
        rows.append({
            "url":url,
            "rank_score":float(r["rank_score"]),
            "candidate_score":float(r["score_num"]),
            "candidate_hits":float(r["hits_num"]),
            "probe_status":status,
            "http_status":http_status,
            "content_type":content_type,
            "response_bytes":bytes_len,
            "response_keyword_score":response_score,
            "error":error,
            "promotion_status":"PROBE_ONLY_NOT_EVENT_EVIDENCE",
        })
        time.sleep(0.05)
    out=pd.DataFrame(rows).sort_values(
        ["response_keyword_score","rank_score"],ascending=False
    )
    op=Path(output_csv); op.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(op,index=False,encoding="utf-8-sig")
    result={
        "input_candidates":int(len(f)),
        "probed":int(len(out)),
        "successful":int((out["probe_status"]=="OK").sum()) if not out.empty else 0,
        "high_response_score":int((out["response_keyword_score"]>=2).sum()) if not out.empty else 0,
        "output_csv":str(op),
    }
    mp=op.with_name(op.stem+"_manifest.json")
    mp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    result["manifest"]=str(mp)
    return result


def acquire_stock_dividend_decision_disclosures_v321(
    dart_client,
    *,
    universe_csv:str,
    start:str,
    end:str,
    output_csv:str,
    audit_csv:str,
    sleep_seconds:float=.05,
) -> dict:
    u=pd.read_csv(universe_csv,dtype=str).fillna("")
    if "code" not in u.columns:
        raise ValueError("universe CSV에 code 열이 필요합니다.")
    if "enabled" in u.columns:
        enabled=u["enabled"].astype(str).str.lower().isin({"1","true","yes","y"})
        u=u[enabled]
    codes=u["code"].astype(str).str.zfill(6).tolist()
    corp_map=dart_client.corp_code_map()
    rows=[]; audit=[]
    end=min(str(end),RESEARCH_SEEN_THROUGH)
    for i,code in enumerate(codes,1):
        corp_code=corp_map.get(code,"")
        if not corp_code:
            audit.append({"code":code,"status":"NO_DART_CORP_CODE","rows":0,"error":""})
            continue
        try:
            disclosures=dart_client.disclosure_list(corp_code,str(start),str(end),page_count=100)
            matched=[]
            for raw in disclosures:
                name=str(raw.get("report_nm",""))
                if any(k in name for k in DIVIDEND_REPORT_KEYWORDS):
                    rcept_dt=str(raw.get("rcept_dt","")).replace("-","")
                    if rcept_dt and rcept_dt<=RESEARCH_SEEN_THROUGH:
                        matched.append(raw)
                        rows.append({
                            "code":code,
                            "corp_code":corp_code,
                            "known_at":rcept_dt,
                            "report_nm":name,
                            "rcept_no":str(raw.get("rcept_no","")),
                            "flr_nm":str(raw.get("flr_nm","")),
                            "verification_source":"OPENDART_DISCLOSURE_LIST",
                            "promotion_status":"OFFICIAL_DECISION_DISCLOSURE_NEEDS_EX_DATE",
                            "raw_json":json.dumps(raw,ensure_ascii=False,sort_keys=True),
                        })
            audit.append({"code":code,"status":"OK","rows":len(matched),"error":""})
        except Exception as exc:
            audit.append({
                "code":code,"status":"FAILED","rows":0,
                "error":f"{type(exc).__name__}: {exc}",
            })
        if sleep_seconds>0:
            time.sleep(sleep_seconds)
    op=Path(output_csv); ap=Path(audit_csv)
    op.parent.mkdir(parents=True,exist_ok=True); ap.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(op,index=False,encoding="utf-8-sig")
    pd.DataFrame(audit).to_csv(ap,index=False,encoding="utf-8-sig")
    return {
        "codes":len(codes),
        "decision_rows":len(rows),
        "failed_codes":sum(1 for x in audit if x["status"]=="FAILED"),
        "output_csv":str(op),
        "audit_csv":str(ap),
    }


def build_stock_dividend_exdate_resolution_queue_v321(
    *,
    refined_amount_candidates_csv:str,
    dividend_decisions_csv:str,
    output_csv:str,
    match_days:int=430,
) -> dict:
    a=pd.read_csv(refined_amount_candidates_csv,dtype=str).fillna("")
    d=pd.read_csv(dividend_decisions_csv,dtype=str).fillna("")
    required_a={"queue_event_id","code","source_reference_date","candidate_cash_amount","candidate_known_at"}
    missing=required_a-set(a.columns)
    if missing:
        raise ValueError("refined amount candidate 누락 열: "+", ".join(sorted(missing)))
    required_d={"code","known_at","report_nm","rcept_no","verification_source"}
    missing=required_d-set(d.columns)
    if missing:
        raise ValueError("dividend decision CSV 누락 열: "+", ".join(sorted(missing)))
    a["code"]=a["code"].astype(str).str.zfill(6)
    d["code"]=d["code"].astype(str).str.zfill(6)
    rows=[]
    for _,r in a.iterrows():
        code=r["code"]
        ref=pd.to_datetime(r["source_reference_date"],format="%Y%m%d",errors="coerce")
        cand=d[d["code"].eq(code)].copy()
        if pd.notna(ref) and not cand.empty:
            dt=pd.to_datetime(cand["known_at"],format="%Y%m%d",errors="coerce")
            cand["distance_days"]=(dt-ref).abs().dt.days
            cand=cand[cand["distance_days"]<=int(match_days)].sort_values(["distance_days","known_at"])
        status="NO_DECISION_DISCLOSURE"
        known_at=""; report_nm=""; rcept_no=""; source=""
        if len(cand)==1:
            c=cand.iloc[0]
            status="UNIQUE_DECISION_DISCLOSURE"
            known_at=c["known_at"]; report_nm=c["report_nm"]; rcept_no=c["rcept_no"]; source=c["verification_source"]
        elif len(cand)>1:
            status=f"AMBIGUOUS_DECISION_DISCLOSURES:{len(cand)}"
        rows.append({
            "queue_event_id":r["queue_event_id"],
            "code":code,
            "source_reference_date":r["source_reference_date"],
            "candidate_cash_amount":r["candidate_cash_amount"],
            "amount_candidate_known_at":r["candidate_known_at"],
            "decision_match_status":status,
            "decision_known_at":known_at,
            "decision_report_nm":report_nm,
            "decision_rcept_no":rcept_no,
            "decision_source":source,
            "effective_date":"",
            "action_type":"CASH_DIVIDEND",
            "adjustment_factor":"1",
            "verification_source":"",
            "verification_reference":"",
            "resolution_status":"UNRESOLVED",
            "next_required_evidence":"OFFICIAL_EX_DATE_OR_RECORD_DATE_MAPPING",
        })
    out=pd.DataFrame(rows)
    op=Path(output_csv); op.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(op,index=False,encoding="utf-8-sig")
    counts=out["decision_match_status"].value_counts().to_dict() if not out.empty else {}
    return {
        "rows":len(out),
        "status_counts":{str(k):int(v) for k,v in counts.items()},
        "output_csv":str(op),
    }
