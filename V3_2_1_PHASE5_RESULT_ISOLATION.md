# V3.2.1 Phase 5 — Research Result Isolation

This phase does not add or retune a model.

## New behavior

`ml-diagnose-v321` now supports:

- `--result-dir`: create an isolated folder for exactly one diagnostic run.
- `--zip-results`: compress that folder after the run.
- SHA-256 manifest for every bundled artifact.
- Refuses to write into a non-empty result directory, preventing accidental mixing with older runs.
- `.env`, DB files, raw acquisition data, and credentials are never bundled by this command.

## Recommended Windows command

```bat
python -m src.main ml-diagnose-v321 --horizon 20 --benchmark-code 069500 --validation-days 252 --test-days 126 --min-train-days 504 --fold-days 126 --embargo-days 20 --commission 0.015 --tax 0.18 --slippage 0.05 --stock-cap 0.15 --industry-cap 0.40 --rank-scope market --output-prefix ml_v321_realpit_h20 --result-dir results\v321_realpit_20260808 --zip-results
```

Expected output:

- `results\v321_realpit_20260808\...`
- `results\v321_realpit_20260808.zip`

The research cutoff remains `20260709`. This packaging feature does not change model selection, features, thresholds, or evaluation semantics.

## Next data-integrity inputs

Total return, corporate actions, and historical universe remain external PIT inputs and must not be fabricated from current values.
