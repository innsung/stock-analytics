from __future__ import annotations

from pathlib import Path

import pandas as pd


def select_market_adjustment_candidates_v321(
    *, candidate_manifest_csv: str, official_candidates_csv: str, output_csv: str,
) -> dict:
    manifest = pd.read_csv(candidate_manifest_csv, dtype=str).fillna("")
    official = pd.read_csv(official_candidates_csv, dtype=str).fillna("")
    receipts = set(manifest.loc[
        manifest["acquisition_status"].eq("OFFICIAL_CANDIDATE_AVAILABLE"), "candidate_rcept_no"
    ].str.strip()) - {""}
    selected = official[official["rcept_no"].isin(receipts)].drop_duplicates("rcept_no").copy()
    target = Path(output_csv); target.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(target, index=False, encoding="utf-8-sig")
    counts = {str(k): int(v) for k, v in selected["action_type_hint"].value_counts().items()}
    return {"manifest_receipts": len(receipts), "selected_candidates": len(selected),
            "action_counts": counts, "output_csv": str(target)}
