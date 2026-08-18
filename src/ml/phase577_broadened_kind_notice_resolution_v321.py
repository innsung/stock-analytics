from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.ml.phase529_kind_market_search_v321 import CONTENTS_URL, EXTERNAL_RE, MAIN_URL, SEARCH_URL, VIEWER_URL
from src.ml.phase572_historical_kind_strict_evidence_v321 import APPLY_DATE, _date, build_historical_kind_strict_evidence_v321


COMPANY_FIELD = re.compile(r"회사명\s*(.*?)\s*2\.\s*주권종류")
OFFICIAL_ALIASES = {"005380": ["현대자동차", "현대차"]}


def _membership_rank(text: str, names: list[str]) -> tuple[int, str]:
    field = COMPANY_FIELD.search(text)
    exact = field.group(1).strip() if field else ""
    if exact in names:
        return 1, exact
    compact = re.sub(r"\s+", "", text)
    member = next((name for name in names if re.sub(r"\s+", "", name) in compact), "")
    return (2, member) if member else (99, "")


def resolve_broadened_kind_notices_v321(
    *, residual_csv: str, prior_discovery_audit_csv: str, candidates_csv: str,
    parsed_decisions_csv: str, discovery_output_csv: str, candidate_audit_csv: str,
    strict_evidence_csv: str, strict_audit_csv: str, timeout: int = 20, session=None,
) -> dict:
    residual = pd.read_csv(residual_csv, dtype=str).fillna("")
    prior = pd.read_csv(prior_discovery_audit_csv, dtype=str).fillna("")
    candidates = pd.read_csv(candidates_csv, dtype=str).fillna("")
    targets = residual[residual["residual_status"].eq("NO_MATCHING_KIND_MARKET_NOTICE")]
    http = session or requests.Session(); http.headers.update({"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,ko;q=0.9"})
    http.get(MAIN_URL,timeout=timeout).raise_for_status()
    selected, audits = [], []
    for target in targets.itertuples(index=False):
        code=str(target.code).zfill(6)
        prior_row=prior[prior["queue_event_id"].eq(target.queue_event_id)]
        company=prior_row.iloc[0]["company_name"] if not prior_row.empty else ""
        names=OFFICIAL_ALIASES.get(code,[company])
        cand=candidates[(candidates["queue_event_id"].eq(target.queue_event_id)) &
                        candidates["candidate_status"].eq("READY_FOR_OFFICIAL_MARKET_VERIFICATION")]
        candidate=cand.iloc[-1]["calendar_prior_trading_day_1"] if not cand.empty else ""
        center=datetime.strptime(candidate,"%Y%m%d")
        response=http.post(SEARCH_URL,data={"method":"searchTotalInfoSub","forward":"searchtotalinfo_detail",
            "fdName":"all_mktact_idx","pageIndex":"1","currentPageSize":"100","scn":"mktact","srchFd":"2",
            "kwd":"배당락","fromData":(center-timedelta(days=10)).strftime("%Y-%m-%d"),
            "toData":(center+timedelta(days=3)).strftime("%Y-%m-%d")},
            headers={"X-Requested-With":"XMLHttpRequest","Referer":MAIN_URL},timeout=timeout)
        response.raise_for_status()
        if (response.encoding or "").lower()=="iso-8859-1" and response.apparent_encoding: response.encoding=response.apparent_encoding
        matches=[]
        for node in BeautifulSoup(response.text,"html.parser").select("dt.img"):
            link=node.select_one("span.subject a"); ids=re.findall(r"\d{14}",link.get("onclick","")) if link else []
            if len(ids)<2 or "배당락" not in link.get_text(" ",strip=True): continue
            issuer_node=node.select_one("strong.name")
            issuer=" ".join(issuer_node.get_text(" ",strip=True).split()) if issuer_node else ""
            if issuer not in names and issuer != "유가증권시장":
                continue
            viewer=VIEWER_URL.format(ids[0]); http.get(viewer,timeout=timeout).raise_for_status()
            contents=http.get(CONTENTS_URL.format(ids[1]),headers={"Referer":viewer},timeout=timeout); contents.raise_for_status()
            urls=EXTERNAL_RE.findall(contents.text)
            if not urls: continue
            try:
                source=http.get(urls[0],headers={"Referer":viewer},timeout=timeout); source.raise_for_status()
            except requests.RequestException as exc:
                audits.append({"queue_event_id":target.queue_event_id,"code":code,"kind_acpt_no":ids[0],
                    "kind_doc_no":ids[1],"rank":99,"parsed_ex_date":"","membership_name":"","selected":False,
                    "error":f"{type(exc).__name__}: {exc}"})
                continue
            if (source.encoding or "").lower()=="iso-8859-1" and source.apparent_encoding: source.encoding=source.apparent_encoding
            text=" ".join(BeautifulSoup(source.text,"html.parser").get_text(" ",strip=True).split())
            applied=_date(APPLY_DATE.search(text)); rank,member=_membership_rank(text,names)
            distance = (datetime.strptime(candidate,"%Y%m%d")-datetime.strptime(applied,"%Y%m%d")).days if applied else 999
            # Calendar dates are search hints only. An explicit official KIND
            # application date may precede the naive prior-session candidate
            # because of exchange settlement/holiday rules.
            valid=rank<99 and 0 <= distance <= 5
            row={"queue_event_id":target.queue_event_id,"code":code,"company_name":company,
                "candidate_ex_date":candidate,"notice_title":link.get_text(" ",strip=True),"kind_acpt_no":ids[0],
                "kind_doc_no":ids[1],"market_source_url":urls[0],"rank":rank,"membership_name":member,
                "parsed_ex_date":applied,"candidate_distance_days":distance,"valid_candidate":valid}
            if valid: matches.append(row)
            audits.append({**row,"selected":False,"error":""})
        if matches:
            best_rank=min(row["rank"] for row in matches); best=[row for row in matches if row["rank"]==best_rank]
            if len(best)==1:
                chosen=best[0]; selected.append({key:chosen[key] for key in ["queue_event_id","code","notice_title",
                    "kind_acpt_no","kind_doc_no","market_source_url"]} |
                    {"company_name":chosen["membership_name"],"candidate_ex_date":chosen["parsed_ex_date"],
                     "discovery_status":"DISCOVERED_OFFICIAL_NOTICE","strict_promotion_status":"NOT_PROMOTED_NOTICE_BODY_PARSE_REQUIRED"})
                for audit in audits:
                    if audit.get("queue_event_id")==target.queue_event_id and audit.get("kind_acpt_no")==chosen["kind_acpt_no"]:
                        audit["selected"]=True
    columns=["queue_event_id","code","company_name","candidate_ex_date","notice_title","kind_acpt_no","kind_doc_no",
             "market_source_url","discovery_status","strict_promotion_status"]
    output=pd.DataFrame(selected,columns=columns)
    op,ap=Path(discovery_output_csv),Path(candidate_audit_csv); op.parent.mkdir(parents=True,exist_ok=True)
    output.to_csv(op,index=False,encoding="utf-8-sig"); pd.DataFrame(audits).to_csv(ap,index=False,encoding="utf-8-sig")
    strict=build_historical_kind_strict_evidence_v321(discovery_csv=str(op),parsed_decisions_csv=parsed_decisions_csv,
        output_csv=strict_evidence_csv,audit_csv=strict_audit_csv,timeout=timeout,session=http) if not output.empty else {"strict_rows":0}
    return {"target_rows":len(targets),"resolved_rows":len(output),"strict_rows":strict["strict_rows"],
            "unresolved_rows":len(targets)-len(output),"discovery_output_csv":str(op),"candidate_audit_csv":str(ap),
            "strict_evidence_csv":strict_evidence_csv,"strict_audit_csv":strict_audit_csv}
