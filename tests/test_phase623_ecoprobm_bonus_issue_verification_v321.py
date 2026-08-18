import sqlite3,pandas as pd
from src.ml.phase623_ecoprobm_bonus_issue_verification_v321 import verify_ecoprobm_bonus_issue_v321
class Dart:
 def document_texts(self,r):return [{"name":"x.xml","text":'<TE ACODE="BFR_CST_CNT">24,530,810</TE><TE ACODE="CST_CNT">73,351,008</TE><TE ACODE="NEW_ASN_CST">3</TE>'}]
def test_verifies_bonus_factor_from_structured_terms_and_calendar(tmp_path):
 pd.DataFrame([{"queue_event_id":"fe87e76e0b26e616df1c","code":"247540","source_reference_date":"20220624","source_description":"권리락(무상증자)"}]).to_csv(tmp_path/"q.csv",index=False);pd.DataFrame([{"code":"247540","rcept_dt":"20220624","report_nm":"권리락(무상증자)","rcept_no":"20220624900454"},{"code":"247540","rcept_dt":"20220614","report_nm":"[기재정정]주요사항보고서(유무상증자결정)","rcept_no":"20220614000068"}]).to_csv(tmp_path/"d.csv",index=False)
 c=sqlite3.connect(tmp_path/"x.db");c.execute("create table stock_prices(code text,date text)");c.executemany("insert into stock_prices values(?,?)",[("247540","20220624"),("247540","20220627")]);c.commit();c.close()
 r=verify_ecoprobm_bonus_issue_v321(Dart(),actionable_queue_csv=str(tmp_path/"q.csv"),disclosures_csv=str(tmp_path/"d.csv"),trading_calendar_db=str(tmp_path/"x.db"),documents_dir=str(tmp_path/"docs"),evidence_output_csv=str(tmp_path/"e.csv"),audit_output_csv=str(tmp_path/"a.csv"),summary_json=str(tmp_path/"s.json"));assert r["strict_evidence_rows"]==1 and r["adjustment_factor"]==4.0
