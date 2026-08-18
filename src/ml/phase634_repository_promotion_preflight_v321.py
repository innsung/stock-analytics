from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def classify_release_path(path: str) -> tuple[str, str]:
    normalized = path.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    if normalized.startswith((".venv", "tmp/")) or name.endswith((".db-shm", ".db-wal", ".pyc")):
        return "EXCLUDE_RUNTIME", "runtime or temporary artifact"
    if normalized.startswith(("src/", "tests/", "docs/", "config/", "scripts/")):
        return "RELEASE_CANDIDATE", "source, test, documentation, or configuration"
    if normalized.startswith("data/raw/v321/events/"):
        return "EVIDENCE_REVIEW", "release evidence requires explicit inclusion decision"
    if name.endswith((".zip", ".csv", ".db", ".joblib")):
        return "EXCLUDE_GENERATED", "generated or binary artifact"
    if name in {"README.md", ".gitignore", ".env.example", "requirements.txt", "requirements-lock.txt"}:
        return "RELEASE_CANDIDATE", "root release metadata"
    return "MANUAL_REVIEW", "scope is not safely inferable"


def build_repository_promotion_preflight_v321(
    *, repository: str, inventory_csv: str, summary_json: str
) -> dict:
    repo = Path(repository).resolve()
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    output = subprocess.run(["git", "status", "--porcelain=v1", "-z"], cwd=repo, check=True, capture_output=True).stdout
    entries = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        text = raw.decode("utf-8", errors="surrogateescape")
        status, path = text[:2], text[3:]
        category, reason = classify_release_path(path)
        entries.append({"git_status": status, "path": path, "category": category, "reason": reason})
    inventory = pd.DataFrame(entries, columns=["git_status", "path", "category", "reason"])
    inventory_path = Path(inventory_csv)
    summary_path = Path(summary_json)
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(inventory_path, index=False, encoding="utf-8-sig")
    counts = inventory["category"].value_counts().to_dict() if len(inventory) else {}
    clean = len(inventory) == 0
    summary = {
        "phase": "V3.2.1 Phase 6.34",
        "repository": str(repo),
        "branch": branch,
        "head": head,
        "promotion_preflight": "PASS" if clean else "HOLD",
        "promotion_blocker": None if clean else "DIRTY_WORKTREE_REQUIRES_EXPLICIT_CURATION",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "changed_paths": len(inventory),
        "category_counts": {key: int(value) for key, value in counts.items()},
        "safe_automatic_commit": False,
        "git_commit_created": False,
        "git_tag_created": False,
        "inventory_csv": str(inventory_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(summary_path)}
