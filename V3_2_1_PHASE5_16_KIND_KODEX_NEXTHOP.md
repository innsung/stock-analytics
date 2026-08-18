# V3.2.1 Phase 5.16 — KRX KIND Cross-check + KODEX Next-hop Discovery

No model change and no persistent DB mutation.

## 1. Cross-check the 47 P1 dividend rows against KRX KIND

The official KIND disclosure viewer is queried by the DART/KRX receipt number already
stored in the Phase 5.15 queue. The parser cross-checks:
- dividend record date
- per-share cash amount
- payment date
- board/decision date

```bat
python -m src.main crosscheck-kind-dividends-v321 --market-exdate-queue-csv data\raw\v321\events\stock_dividend_market_exdate_verification_queue_v321.csv --output-csv data\raw\v321\events\kind_dividend_crosscheck_v321.csv --audit-csv data\raw\v321\events\kind_dividend_crosscheck_audit.csv
```

A record-date/amount match strengthens event identity, but it still does not prove the
market EX_DATE. Nothing is promoted to strict cash evidence here.

## 2. Discover KODEX next-hop calls inside saved high-signal bodies

The 10 Phase 5.13 response bodies contained no direct structured date/amount schema.
Phase 5.16 therefore scans them for AJAX/fetch/action/API next-hop URLs.

```bat
python -m src.main discover-kodex-next-hops-v321 --bodies-dir data\raw\v321\events\kodex_069500\high_signal\bodies --output-csv data\raw\v321\events\kodex_069500\high_signal\kodex_next_hop_candidates_v321.csv
```

These URLs are discovery artifacts only and are not automatically invoked or promoted.

## Safety
- research cutoff remains 2026-07-09
- no record-date-to-ex-date assumption
- KIND record-date match is not EX_DATE evidence
- no discovered KODEX next-hop is evidence until separately probed and parsed
- release ZIP contains no `data/`, DB, `.env`, or `results/`
