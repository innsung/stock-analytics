# V3.2.1 Phase 5.2 — Persistent Data Protection + Total Return Foundation

No new model or retuning is introduced.

## Persistent data protection

The release ZIP contains **no `data/` directory** and no `.env`. Direct copy/paste therefore cannot overwrite the local SQLite database, raw KRX data, checkpoints, feature store, labels, or prior result bundles.

New commands:

```bat
python -m src.main db-health-v321 --benchmark-code 069500 --output-json data\protection\health.json
python -m src.main backup-db-v321 --output-dir data\backup --label before_update
```

`ml-diagnose-v321` now runs a persistent-data guard before evaluation. If price, valuation, feature, or label data is missing, it stops without collecting or rebuilding anything automatically.

`APPLY_UPDATE_SAFE.cmd` creates a pre-update SQLite backup and excludes `data`, `.env`, `results`, virtualenvs, Git metadata, and DB files from copying.

## Total Return Foundation

A new builder can derive a canonical total-return index from local closing prices plus **verified** cash distributions and supported capital actions.

Supported derived actions:
- SPLIT
- REVERSE_SPLIT
- BONUS
- CASH_DIVIDEND
- ETF_DISTRIBUTION

Complex actions such as RIGHTS, MERGER, and SPINOFF are rejected for derived total return; use an externally verified total-return index instead.

The builder requires a coverage JSON that explicitly attests that cash distributions and capital actions are complete for the covered codes and interval. The provided example intentionally sets both completion flags to `false`, preventing accidental VERIFIED status.

```bat
python -m src.main build-total-return-v321 ^
  --corporate-actions-csv data\raw\v321\corporate_actions.csv ^
  --coverage-json config\total_return_coverage_v321.json ^
  --output-csv data\v321_foundation\total_return_history_v321.csv ^
  --benchmark-code 069500
```

After a VERIFIED total-return file exists, pass it to diagnostics with:

```bat
--total-return-csv data\v321_foundation\total_return_history_v321.csv
```

Research cutoff remains `20260709`.
