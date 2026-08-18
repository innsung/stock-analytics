# V3.2.1 Phase 5.11 — KODEX Dynamic Endpoint Discovery + Dividend Refinement

This phase does not change the model or mutate the persistent DB.

## KODEX dynamic discovery

The official KODEX product page currently exposes the product and distribution section,
but actual payment history may be populated dynamically. The new command downloads the
official HTML plus same-origin JavaScript files and extracts URL/AJAX/API candidates
whose surrounding code mentions distribution/dividend/분배금-related terms.

```bat
python -m src.main discover-kodex-dynamic-endpoints-v321 --product-url https://m.samsungfund.com/etf/product/view.do?id=2ETF01 --output-dir data\raw\v321\events\kodex_069500\dynamic
```

Outputs:
- `kodex_dynamic_endpoint_candidates_v321.csv`
- `kodex_dynamic_script_audit.csv`
- `kodex_dynamic_discovery_manifest.json`

Endpoint candidates are discovery artifacts only. They are never treated as historical
distribution evidence until their response schema and dates are separately verified.

## Stock dividend refinement

The prior Phase 5.8 logic considered both `reference-year - 1` and `reference-year`
together, which could create artificial two-value ambiguity. Phase 5.11 changes the
order conservatively:

1. use business year `Y-1` first for a disclosure dated in year `Y`;
2. if `Y-1` has exactly one valid common-stock cash-per-share amount, keep it;
3. only if `Y-1` has none, fall back to year `Y`;
4. multiple amounts within the same business year remain ambiguous.

```bat
python -m src.main refine-stock-dividend-candidates-v321 --dividend-facts-csv data\raw\v321\events\dividend_disclosure_facts.csv --verification-csv data\raw\v321\events\event_verification_v321.csv --output-csv data\raw\v321\events\stock_cash_amount_candidates_refined_v321.csv --audit-csv data\raw\v321\events\stock_cash_amount_candidates_refined_audit.csv
```

This only improves amount candidates. An official ex/effective date is still required
before strict cash evidence can be created.

## Safety

- research cutoff remains 2026-07-09
- no policy date is converted to a historical event
- no endpoint candidate is auto-invoked as evidence
- no ambiguous dividend amount is forced to a value
- release ZIP contains no `data/`, DB, `.env`, or `results/`
