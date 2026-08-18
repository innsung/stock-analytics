from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.ml.phase529_kind_market_search_v321 import CONTENTS_URL, EXTERNAL_RE, MAIN_URL, SEARCH_URL, VIEWER_URL
from src.ml.phase572_historical_kind_strict_evidence_v321 import APPLY_DATE, _date, build_historical_kind_strict_evidence_v321


COMPANY_NAMES = {"005930":"삼성전자", "006400":"삼성SDI", "012330":"현대모비스"}
COMPANY_FIELD = re.compile(r"회사명\s*(.*?)\s*2\.\s*주권종류")


def recover_pre_exdate_dividend_evidence_v321(
    *, residual_csv: str, parsed_decisions_csv: str, candidates_csv: str,
    provenance_audit_csv: str, discovery_output_csv: str, discovery_audit_csv: str,
    strict_evidence_csv: str, strict_audit_csv: str, timeout: int = 20, session=None,
) -> dict:
    residual=pd.read_csv(residual_csv,dtype=str).fillna("")
    parsed=pd.read_csv(parsed_decisions_csv,dtype=str).fillna("")
    candidates=pd.read_csv(candidates_csv,dtype=str).fillna("")
    targets=residual[residual["residual_status"].eq("DECISION_DISCLOSED_AFTER_EXDATE")]
    provenance=[]; recovered=[]
    for target in targets.itertuples(index=False):
        code=str(target.code).zfill(6)
        docs=parsed[(parsed["queue_event_id"].eq(target.queue_event_id)) &
                    parsed["parse_status"].eq("PARSED_DECISION_TERMS")].copy()
        if docs.empty: continue
        docs["record_clean"]=docs["dividend_record_date"].str.replace("-","",regex=False)
        latest_record=docs["record_clean"].max(); event=docs[docs["record_clean"].eq(latest_record)].copy()
        latest=event.sort_values("rcept_no").iloc[-1]
        same=event[(event["common_cash_dividend_per_share"].eq(latest["common_cash_dividend_per_share"])) &
                   (event["board_decision_date"].eq(latest["board_decision_date"]))]
        first_known=same["rcept_dt"].min()
        cand=candidates[(candidates["queue_event_id"].eq(target.queue_event_id)) &
                        candidates["record_date"].eq(latest_record) &
                        candidates["common_cash_dividend_per_share"].eq(latest["common_cash_dividend_per_share"])]
        hint=cand.iloc[-1]["calendar_prior_trading_day_1"] if not cand.empty else ""
        recoverable=bool(first_known and hint and first_known<=hint)
        status="EARLY_ORIGINAL_FILING_RECOVERED" if recoverable else "NO_PRE_EXDATE_AMOUNT_DISCLOSURE"
        provenance.append({"queue_event_id":target.queue_event_id,"code":code,"record_date":latest_record,
            "cash_amount":latest["common_cash_dividend_per_share"],"canonical_rcept_no":latest["rcept_no"],
            "canonical_rcept_dt":latest["rcept_dt"],"first_known_at":first_known,"calendar_search_hint":hint,
            "identical_term_filings":len(same),"provenance_status":status})
        if recoverable: recovered.append((target,code,COMPANY_NAMES.get(code,""),hint))
    pa=Path(provenance_audit_csv); pa.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(provenance).to_csv(pa,index=False,encoding="utf-8-sig")
    http=session or requests.Session(); http.headers.update({"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
    if recovered: http.get(MAIN_URL,timeout=timeout).raise_for_status()
    selected=[]; audits=[]
    for target,code,company,hint in recovered:
        center=datetime.strptime(hint,"%Y%m%d")
        response=http.post(SEARCH_URL,data={"method":"searchTotalInfoSub","forward":"searchtotalinfo_detail",
            "fdName":"all_mktact_idx","pageIndex":"1","currentPageSize":"100","scn":"mktact","srchFd":"2","kwd":"배당락",
            "fromData":(center-timedelta(days=10)).strftime("%Y-%m-%d"),"toData":(center+timedelta(days=3)).strftime("%Y-%m-%d")},
            headers={"X-Requested-With":"XMLHttpRequest","Referer":MAIN_URL},timeout=timeout); response.raise_for_status()
        if (response.encoding or "").lower()=="iso-8859-1" and response.apparent_encoding: response.encoding=response.apparent_encoding
        matches=[]
        for node in BeautifulSoup(response.text,"html.parser").select("dt.img"):
            issuer_node=node.select_one("strong.name"); issuer=issuer_node.get_text(" ",strip=True) if issuer_node else ""
            if issuer!=company: continue
            link=node.select_one("span.subject a"); ids=re.findall(r"\d{14}",link.get("onclick","")) if link else []
            if len(ids)<2 or "배당락" not in link.get_text(" ",strip=True): continue
            viewer=VIEWER_URL.format(ids[0]); http.get(viewer,timeout=timeout).raise_for_status()
            contents=http.get(CONTENTS_URL.format(ids[1]),headers={"Referer":viewer},timeout=timeout); contents.raise_for_status()
            urls=EXTERNAL_RE.findall(contents.text)
            if not urls: continue
            source=http.get(urls[0],headers={"Referer":viewer},timeout=timeout); source.raise_for_status()
            if (source.encoding or "").lower()=="iso-8859-1" and source.apparent_encoding: source.encoding=source.apparent_encoding
            text=" ".join(BeautifulSoup(source.text,"html.parser").get_text(" ",strip=True).split())
            field=COMPANY_FIELD.search(text); exact=field.group(1).strip() if field else ""; applied=_date(APPLY_DATE.search(text))
            valid=exact==company and bool(applied)
            audits.append({"queue_event_id":target.queue_event_id,"code":code,"company_name":company,
                "kind_acpt_no":ids[0],"kind_doc_no":ids[1],"parsed_company":exact,"parsed_ex_date":applied,
                "source_url":urls[0],"valid":valid})
            if valid: matches.append((link.get_text(" ",strip=True),ids[0],ids[1],urls[0],applied))
        if len(matches)==1:
            title,acpt,doc,url,applied=matches[0]
            selected.append({"queue_event_id":target.queue_event_id,"code":code,"company_name":company,
                "candidate_ex_date":applied,"notice_title":title,"kind_acpt_no":acpt,"kind_doc_no":doc,
                "market_source_url":url,"discovery_status":"DISCOVERED_OFFICIAL_NOTICE",
                "strict_promotion_status":"NOT_PROMOTED_NOTICE_BODY_PARSE_REQUIRED"})
    columns=["queue_event_id","code","company_name","candidate_ex_date","notice_title","kind_acpt_no","kind_doc_no",
             "market_source_url","discovery_status","strict_promotion_status"]
    output=pd.DataFrame(selected,columns=columns); op,da=Path(discovery_output_csv),Path(discovery_audit_csv)
    output.to_csv(op,index=False,encoding="utf-8-sig"); pd.DataFrame(audits).to_csv(da,index=False,encoding="utf-8-sig")
    strict=build_historical_kind_strict_evidence_v321(discovery_csv=str(op),parsed_decisions_csv=parsed_decisions_csv,
        output_csv=strict_evidence_csv,audit_csv=strict_audit_csv,timeout=timeout,session=http) if not output.empty else {"strict_rows":0}
    return {"target_rows":len(targets),"provenance_recovered_rows":len(recovered),
            "no_pre_exdate_disclosure_rows":len(targets)-len(recovered),"official_notices_resolved":len(output),
            "strict_rows":strict["strict_rows"],"provenance_audit_csv":str(pa),"discovery_output_csv":str(op),
            "strict_evidence_csv":strict_evidence_csv}
