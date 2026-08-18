# V3.2.1 Historical Data Acquisition Phase 4.2

Phase 4.2 hardens the KRX historical valuation acquisition path without changing model selection or research parameters.

## What changed

- Annual chunks: each ticker is requested one calendar year at a time.
- HTTP timeout: pykrx/requests calls get a default timeout (`--timeout-seconds`, default 45 seconds).
- Retry: failed chunks are retried with exponential backoff (`--max-retries`, default 3 attempts; `--retry-backoff-seconds`, default 2 seconds).
- Checkpoint: every successful annual chunk is immediately written under `data/raw/v321/checkpoints/valuation/` with a `.done.json` completion marker.
- Resume: rerunning the same command skips completed chunks and continues only missing/failed chunks. Use `--no-resume` only when an intentional fresh request is required.
- Progress: ticker/chunk/overall progress, retries, rows, and resume/skip state are printed immediately.
- Ctrl+C safety: completed checkpoint files remain on disk. Rerun the same command to continue.
- Partial-acquisition guard: any failed chunk prevents the acquisition from being marked fully verified.

## Recommended Windows command

Run as one line to avoid CMD caret/copy issues:

```bat
python -m src.main acquire-historical-data-v321 --universe-csv config\universe_kr_24.example.csv --start 20200101 --end 20260709 --frequency m --output-dir data\raw\v321 --timeout-seconds 45 --max-retries 3 --retry-backoff-seconds 2
```

Typical progress:

```text
[1/24] 005930 [1/7] 2020 (1/168) 조회 시도 1/3...
[1/24] 005930 [1/7] 2020 (1/168) OK 12행 / checkpoint 저장
[1/24] 005930 [2/7] 2021 (2/168) 조회 시도 1/3...
...
```

After interruption, rerun the exact same command:

```text
[1/24] 005930 [1/7] 2020 (1/168) RESUME/SKIP 12행
```

## Files

- `data/raw/v321/checkpoints/valuation/*.csv`: completed annual chunk payloads
- `data/raw/v321/checkpoints/valuation/*.done.json`: atomic completion markers
- `data/raw/v321/valuation_snapshots.csv`: merged canonical acquisition output
- `data/raw/v321/valuation_acquisition_audit.csv`: chunk-level status/attempt/error audit
- `data/raw/v321/provider_status.json`: credential-safe provider preflight status
- `data/raw/v321/acquisition_manifest.json`: acquisition settings and completeness summary

## Safety

- `research_seen_through = 20260709` remains fixed.
- No post-cutoff data are admitted for retuning.
- No current valuation is backfilled into historical dates.
- Adjusted OHLCV is not promoted to dividend-inclusive total return.
- Failed chunks are not given completion markers.
- KRX credentials remain in `.env`; `.env` is excluded by `.gitignore`.
