# V3.2.1 Phase 5.6 — OpenDART Official Event Candidate Acquisition

No model or persistent DB changes are made.

This phase queries detailed OpenDART major-event endpoints for:
- bonus issue decisions (`fricDecsn`)
- merger decisions (`cmpMgDecsn`)
- company division decisions (`cmpDvDecsn`)
- division-merger decisions (`cmpDvmgDecsn`)
- stock exchange/transfer decisions (`stkExtrDecsn`)

The result is an **official candidate evidence layer**, not strict Total Return evidence.
OpenDART may provide legal/record dates such as new-share record date or division date,
but these are not silently converted into a market ex-date/price-adjustment date.

## Acquire candidates

```bat
python -m src.main acquire-official-event-candidates-v321 --universe-csv config\universe_kr_24.example.csv --start 20200101 --end 20260709 --output-dir data\raw\v321\events\official_candidates
```

## Enrich the Phase 5.5 evidence template

```bat
python -m src.main enrich-official-evidence-v321 --evidence-template-csv data\raw\v321\events\official_event_evidence_v321.csv --candidate-csv data\raw\v321\events\official_candidates\official_event_candidates_v321.csv --output-csv data\raw\v321\events\official_event_evidence_enriched_v321.csv
```

The enriched file contains candidate summaries for review, but strict evidence fields
remain blank until an actual ex/effective date and factor/cash amount are independently
verified. Therefore it cannot accidentally pass `resolve-official-events-v321`.

The distribution ZIP contains no `data/`, DB, `.env`, or `results/`.
