from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.ml.phase635_release_curation_manifest_v321 import ROOT_METADATA, classify_curation_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_curated_release_payload_v321(
    *, repository: str, resolution_summary_json: str, payload_zip: str, manifest_csv: str, summary_json: str
) -> dict:
    repo = Path(repository).resolve()
    resolution = json.loads(Path(resolution_summary_json).read_text(encoding="utf-8"))
    if resolution.get("curation_resolution") != "PASS" or resolution.get("remaining_manual_review") != 0:
        raise ValueError("Phase 6.36 curation resolution is not complete")

    files: set[Path] = set()
    for root_name in ("src", "database", "tests", "docs", "config", "scripts"):
        root = repo / root_name
        if root.is_dir():
            files.update(path for path in root.rglob("*") if path.is_file())
    files.update(repo / name for name in ROOT_METADATA if (repo / name).is_file())
    files.update(path for pattern in ("*.md", "*.txt", "*.cmd", "*.bat") for path in repo.glob(pattern) if path.is_file())

    included = []
    excluded = []
    for path in sorted(files, key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(repo).as_posix()
        decision, reason = classify_curation_path(relative)
        if relative == "config/valuation_snapshots_v321.csv":
            decision, reason = "EXCLUDE_DUPLICATE_TEMPLATE", "duplicate placeholder"
        elif relative.endswith(".phase516bak"):
            decision, reason = "EXCLUDE_SUPERSEDED_BACKUP", "superseded source backup"
        row = {"path": relative, "decision": decision, "reason": reason, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
        if decision == "PROPOSE_INCLUDE":
            included.append(row)
        else:
            excluded.append(row)
    if any(row["decision"] == "MANUAL_REVIEW" for row in excluded):
        raise ValueError("Curated payload contains unresolved manual-review paths")

    payload_path, manifest_path, summary_path = Path(payload_zip), Path(manifest_csv), Path(summary_json)
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(included).to_csv(manifest_path, index=False, encoding="utf-8-sig")
    with zipfile.ZipFile(payload_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for row in included:
            archive.write(repo / row["path"], arcname=row["path"])
        archive.write(manifest_path, arcname="RELEASE_PAYLOAD_MANIFEST.csv")
    with zipfile.ZipFile(payload_path, "r") as archive:
        bad_entry = archive.testzip()
        entry_count = len(archive.infolist())
    summary = {
        "phase": "V3.2.1 Phase 6.37",
        "release_id": "V3.2.1-RC1",
        "payload_status": "PASS" if bad_entry is None and entry_count == len(included) + 1 else "FAIL",
        "included_files": len(included),
        "excluded_files": len(excluded),
        "zip_entries": entry_count,
        "zip_sha256": _sha256(payload_path),
        "zip_size_bytes": payload_path.stat().st_size,
        "payload_zip": str(payload_path),
        "manifest_csv": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "git_commit_created": False,
        "git_tag_created": False,
        "deployment_performed": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if summary["payload_status"] != "PASS":
        raise ValueError(f"Phase 6.37 payload verification failed: {bad_entry}")
    return summary | {"summary_json": str(summary_path)}
