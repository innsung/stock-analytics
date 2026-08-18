from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_manual_curation_path(repo: Path, relative: str) -> tuple[str, str, str]:
    path = repo / relative
    if relative == "config/valuation_snapshots_v321.csv":
        template = repo / "config/valuation_snapshots_v321.template.csv"
        if template.is_file() and path.read_bytes() == template.read_bytes():
            return "EXCLUDE_DUPLICATE_TEMPLATE", "byte-identical placeholder duplicate of safe template", str(template.relative_to(repo).as_posix())
    if relative.endswith(".phase516bak"):
        current = repo / relative.removesuffix(".phase516bak")
        if current.is_file() and current.stat().st_size >= path.stat().st_size and _sha256(current) != _sha256(path):
            return "EXCLUDE_SUPERSEDED_BACKUP", "older backup superseded by current tested source", str(current.relative_to(repo).as_posix())
    return "MANUAL_REVIEW", "no fail-closed resolution rule matched", ""


def build_manual_curation_resolution_v321(
    *, repository: str, curation_manifest_csv: str, output_csv: str, audit_csv: str, summary_json: str
) -> dict:
    repo = Path(repository).resolve()
    manifest = pd.read_csv(curation_manifest_csv, dtype=str).fillna("")
    manual = manifest.loc[manifest["decision"].eq("MANUAL_REVIEW")]
    audit_rows = []
    for index, row in manual.iterrows():
        decision, reason, replacement = resolve_manual_curation_path(repo, row["path"])
        manifest.loc[index, "decision"] = decision
        manifest.loc[index, "reason"] = reason
        audit_rows.append({"path": row["path"], "decision": decision, "reason": reason, "replacement": replacement})
    audit = pd.DataFrame(audit_rows, columns=["path", "decision", "reason", "replacement"])
    unresolved = int(manifest["decision"].eq("MANUAL_REVIEW").sum())
    output_path, audit_path, summary_path = Path(output_csv), Path(audit_csv), Path(summary_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(output_path, index=False, encoding="utf-8-sig")
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    counts = manifest["decision"].value_counts().to_dict()
    summary = {
        "phase": "V3.2.1 Phase 6.36",
        "curation_resolution": "PASS" if unresolved == 0 and len(manual) == 3 else "HOLD",
        "input_manual_review": len(manual),
        "resolved_manual_review": int(len(manual) - unresolved),
        "remaining_manual_review": unresolved,
        "decision_counts": {key: int(value) for key, value in counts.items()},
        "files_deleted": 0,
        "files_staged": 0,
        "git_commit_created": False,
        "git_tag_created": False,
        "output_manifest_sha256": _sha256(output_path),
        "output_csv": str(output_path),
        "audit_csv": str(audit_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if summary["curation_resolution"] != "PASS":
        raise ValueError(f"Phase 6.36 manual curation resolution incomplete: {unresolved} unresolved")
    return summary | {"summary_json": str(summary_path)}
