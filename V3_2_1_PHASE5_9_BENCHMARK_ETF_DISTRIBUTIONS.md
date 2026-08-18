# V3.2.1 Phase 5.9 — Benchmark ETF Distribution Integration

This phase fixes a structural gap discovered in Phase 5.8: the original 399-event
verification queue was built from the 24-stock research universe, so benchmark ETF
069500 had no cash-distribution queue rows.

The phase does not change the model and does not mutate the persistent DB.

## Official source policy

KODEX 200 (069500) is managed by Samsung Asset Management. The issuer product page
states that distributions are paid and gives the distribution policy, but the policy
must not be treated as proof that a cash distribution actually occurred on every
scheduled period. Actual historical distribution rows must be supplied from an
official issuer/KRX record.

## 1. Create the official 069500 distribution import sheet

```bat
python -m src.main prepare-benchmark-etf-distributions-v321 --output-csv data\raw\v321\events\benchmark_etf_distributions_069500.csv --code 069500
```

The file is intentionally empty. Populate actual historical rows with:
- record_date
- ex_date
- pay_date
- announced_at
- cash_amount
- currency=KRW
- issuer
- verification_source
- verification_reference
- source_url

No quarterly events are fabricated from the fund's stated policy.

## 2. Strict validation

```bat
python -m src.main validate-benchmark-etf-distributions-v321 --official-csv data\raw\v321\events\benchmark_etf_distributions_069500.csv --strict-evidence-csv data\raw\v321\events\benchmark_etf_distribution_strict_evidence_v321.csv --audit-csv data\raw\v321\events\benchmark_etf_distribution_audit.csv --code 069500
```

Strict PIT requires `announced_at <= ex_date <= 20260709`.

## 3. Add verified ETF events to the Phase 5.4 verification universe

```bat
python -m src.main inject-benchmark-etf-events-v321 --strict-evidence-csv data\raw\v321\events\benchmark_etf_distribution_strict_evidence_v321.csv --verification-csv data\raw\v321\events\event_verification_v321.csv --queue-registry-csv data\raw\v321\events\event_verification_v321_queue_registry.csv --output-verification-csv data\raw\v321\events\event_verification_with_benchmark_v321.csv --output-registry-csv data\raw\v321\events\event_verification_with_benchmark_queue_registry.csv
```

This preserves the original stock queue and appends deterministic benchmark ETF
queue IDs. The benchmark is no longer omitted from cash-distribution coverage.

## 4. Stock dividend-resolution summary

```bat
python -m src.main summarize-stock-dividend-resolution-v321 --amount-candidates-csv data\raw\v321\events\stock_cash_amount_candidates_v321.csv --amount-audit-csv data\raw\v321\events\stock_cash_amount_candidates_audit.csv --output-json data\raw\v321\events\stock_dividend_resolution_summary_v321.json
```

Missing or ambiguous stock cash amounts remain unresolved and are never converted to
zero.

## Safety

- No synthetic ETF quarterly distributions.
- No price-gap dividend inference.
- No late announcement is accepted as strict PIT evidence.
- Research cutoff remains 2026-07-09.
- ZIP contains no `data/`, DB, `.env`, or `results/`.
