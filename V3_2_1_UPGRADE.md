# V3.2.1 — Common Risk Overlay & Validation Semantics

V3.2.1 is **not a new model version**. It keeps the V3.1 Champion and the V3.2 five-candidate tournament intact, and fixes evaluation/risk/PIT semantics before any V3.3 model work.

## 1. Common risk management for every strategy

The Champion and all Challengers now follow the same portfolio path:

1. model score
2. financial eligibility gate
3. momentum entry gate
4. loss-streak overlay
5. hard 15% single-stock cap
6. hard 40% industry cap
7. market-regime exposure cap
8. unallocated capital remains cash

Default risk semantics:

- minimum target: 7 eligible stocks
- single stock: at most 15%
- industry: at most 40%
- if fewer than 7 names qualify, do not weaken the filters; leave the missing amount in cash
- after two consecutive losing holding periods for a name, its next new target weight is cut by 50%
- after three consecutive losing holding periods, the name is excluded for one rebalance period
- market exposure: 100% in up regime, 70% neutral, 40% down regime
- live orders remain blocked

Hard constraints are audited for **every validation and published-test interval**, not only aggregate summaries.

## 2. Corrected validation semantics

V3.2.1 separates:

- cumulative outperformance versus both benchmarks
- simultaneous period-by-period wins versus both benchmarks

The simultaneous dual-benchmark win-rate threshold is 60%.

Nested selection now requires at least 3 completed internal folds for the criterion to pass. The default 252-day validation / 126-day fold setup is intended to produce 3–4+ internal folds when sufficient history exists.

New fixation diagnostics:

- portfolio Jaccard similarity between consecutive rebalances
- mean turnover
- maximum individual-stock held rate
- separate portfolio-fixation and individual-stock-fixation flags

New outlier stress test:

- identify the largest positive stock contributor
- remove that stock's contribution from every affected period
- recompute cumulative return, benchmark excess returns, and simultaneous dual-win rate

Outputs:

- `*_fixation_audit.csv`
- `*_hard_constraint_audit.csv`
- `*_outlier_contribution_stress.csv`

## 3. Strict financial PIT audit

`FULL_PIT_VERIFIED` is now impossible when valuation facts are used without a valid `valuation_snapshot_date`.

The audit checks and reports:

- financial disclosure observation date
- valuation snapshot observation date
- observed PER
- observed PBR
- observed market capitalization from `valuation_snapshots`
- whether the underlying valuation source row actually exists
- whether financial characteristics are used by the diagnostics
- explicit reasons for rows with no stored financial or valuation fact

Statuses:

- `FINANCIAL_DISCLOSURE_PIT_PARTIAL`
- `FULL_PIT_VERIFIED`

## 4. Raw-data priority remains ahead of model expansion

The existing V3.x inputs already reserve the following data paths:

- historical universe inclusion/deletion, listing/delisting: `universe_history_v3.template.csv`
- corporate actions and correction factors: `corporate_actions.template.csv`
- cash dividends / ETF distributions: corporate-action types `CASH_DIVIDEND`, `ETF_DISTRIBUTION`
- corrected price / total-return history: `total_return_history.template.csv`
- historical valuation snapshots: database table `valuation_snapshots`

These inputs must be completed with verifiable historical sources before any V3.3 model expansion. Trading-suspension history should be added as a dedicated PIT input rather than inferred from missing prices.

## 5. Future sealed-test maintenance

Research boundary is frozen:

- `research_seen_through = 20260709`
- observations after `20260710` are not allowed to retune V3.2.1
- daily shadow operation may continue
- actual/live orders remain blocked
- the existing 2026 public test is treated as already seen, not fresh evidence
- a normal new sealed-test decision is expected only after roughly 126 new non-overlapping evaluation dates and their 20-trading-day future returns are complete (around February 2027 under the current plan)

## Command

```bash
python -m src.main ml-diagnose-v321 \
  --horizon 20 \
  --benchmark-code 069500 \
  --validation-days 252 \
  --test-days 126 \
  --min-train-days 504 \
  --fold-days 126 \
  --embargo-days 20 \
  --commission 0.015 \
  --tax 0.18 \
  --slippage 0.05 \
  --stock-cap 0.15 \
  --industry-cap 0.40 \
  --rank-scope market \
  --output-prefix ml_v321_h20
```

`--test-days126` is intentionally invalid argparse syntax and returns a command-line error. The valid form is `--test-days 126`.
