# V3.2.1 Data Integrity Phase 3

This phase does not add or retune a model. `research_seen_through` remains frozen at `20260709`.

## Added

- Strict canonical ingestion for historical valuation snapshots, total-return index history, corporate actions, and historical universe membership.
- `build-data-foundation-v321` command writes verified canonical files plus `foundation_audit.csv` and `foundation_manifest.json`.
- Placeholder/example sources are rejected; rows after 2026-07-09 are rejected.
- No backfill, interpolation, or current-value retrofitting is performed.
- Historical valuation `known_at` is now persisted in `valuation_snapshot_meta` and propagated to `ml_features.valuation_known_at`.
- FULL PIT now requires valuation `snapshot_date`, `known_at`, and a matching source row.
- Backward compatibility is preserved for the existing 10-column `valuation_snapshots` table.

## Build canonical data foundation

```bat
python -m src.main build-data-foundation-v321 ^
  --valuation-csv data/raw/valuation_snapshots.csv ^
  --total-return-csv data/raw/total_return_history.csv ^
  --corporate-actions-csv data/raw/corporate_actions.csv ^
  --universe-history-csv data/raw/universe_history.csv ^
  --output-dir data/v321_foundation
```

Every supplied input must pass strict PIT validation. It is valid to run the command with only the datasets currently available; the manifest then records a partial foundation instead of pretending the missing datasets are verified.

## Import verified valuation and rebuild features

```bat
python -m src.main import-valuation-snapshots-v321 --csv data/v321_foundation/valuation_snapshots_v321.csv
python -m src.main build-feature-store --universe-csv config/universe_kr_24.example.csv --benchmark-code 069500
```

## Diagnose with canonical Phase 3 inputs

```bat
python -m src.main ml-diagnose-v321 --horizon 20 --benchmark-code 069500 --validation-days 252 --test-days 126 --min-train-days 504 --fold-days 126 --embargo-days 20 --commission 0.015 --tax 0.18 --slippage 0.05 --stock-cap 0.15 --industry-cap 0.40 --rank-scope market --universe-history-csv data/v321_foundation/universe_history_v321.csv --total-return-csv data/v321_foundation/total_return_history_v321.csv --corporate-actions-csv data/v321_foundation/corporate_actions_v321.csv --output-prefix ml_v321_phase3_h20
```

Do not point the diagnostic at a canonical file that was not produced by the foundation command. Missing datasets should remain missing until verifiable source history is obtained.
