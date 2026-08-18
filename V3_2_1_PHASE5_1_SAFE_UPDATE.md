# V3.2.1 Phase 5.1 — Result Bundling Fix + Safe Source Update

## Fixed
The Phase 5 CLI created `diagnostic_prefix` under `--result-dir`, but accidentally passed the old `args.output_prefix` to `run_ml_diagnostics_v321`. Diagnostics therefore went to the project root while the bundler inspected an empty result folder.

Phase 5.1 passes the resolved `diagnostic_prefix` into diagnostics and refuses to create a ZIP unless at least 20 diagnostic artifacts are present.

## DB safety
The distribution ZIP intentionally contains **no `data/` directory**, no SQLite DB, no `.env`, no raw acquisition files, and no `results/`.

Therefore normal copy/paste extraction cannot overwrite:
- `data\stock_analytics.db`
- `data\raw\v321`
- valuation checkpoints
- `.env`
- prior result ZIPs

For the safest update, extract this release to a temporary folder and run:

```bat
APPLY_UPDATE_SAFE.cmd C:\dev\stock-analytics
```

The script uses `robocopy` while explicitly excluding `data`, `results`, `.env`, `.venv`, `.git`, and database files.

## Diagnostic command

```bat
python -m src.main ml-diagnose-v321 --horizon 20 --benchmark-code 069500 --validation-days 252 --test-days 126 --min-train-days 504 --fold-days 126 --embargo-days 20 --commission 0.015 --tax 0.18 --slippage 0.05 --stock-cap 0.15 --industry-cap 0.40 --rank-scope market --output-prefix ml_v321_realpit_h20 --result-dir results\v321_realpit_20260808_p51 --zip-results
```

Expected result:
- diagnostic CSV/JSON files inside `results\v321_realpit_20260808_p51\`
- bundle manifest with nonzero `file_count`
- `results\v321_realpit_20260808_p51.zip`

The research cutoff remains 2026-07-09 and no model is added or retuned.
