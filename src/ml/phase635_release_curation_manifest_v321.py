from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT_METADATA = {"README.md", ".gitignore", ".env.example", "requirements.txt", "requirements-lock.txt"}


def classify_curation_path(path: str) -> tuple[str, str]:
    normalized = path.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    if "/__pycache__/" in f"/{normalized}" or name.endswith((".pyc", ".db-shm", ".db-wal")):
        return "PROPOSE_EXCLUDE", "runtime artifact"
    if normalized.startswith("src/") and name.endswith(".py"):
        return "PROPOSE_INCLUDE", "application source"
    if normalized.startswith("database/") and name.endswith(".py"):
        return "PROPOSE_INCLUDE", "database application source"
    if normalized.startswith("tests/") and name.endswith(".py"):
        return "PROPOSE_INCLUDE", "test source"
    if normalized.startswith("docs/") and name.endswith(".md"):
        return "PROPOSE_INCLUDE", "versioned documentation"
    if normalized.startswith("scripts/") and name.endswith((".py", ".bat", ".cmd")):
        return "PROPOSE_INCLUDE", "operational script"
    if normalized.startswith("config/"):
        if ".template." in name or ".example." in name or name.endswith(".py"):
            return "PROPOSE_INCLUDE", "configuration code or safe template"
        return "MANUAL_REVIEW", "live configuration data"
    if normalized in ROOT_METADATA:
        return "PROPOSE_INCLUDE", "root release metadata"
    if "/" not in normalized and name.endswith((".md", ".txt", ".cmd", ".bat")):
        return "PROPOSE_INCLUDE", "root release documentation or operational script"
    return "MANUAL_REVIEW", "not covered by release allowlist"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release_curation_manifest_v321(
    *, repository: str, preflight_summary_json: str, output_csv: str, summary_json: str
) -> dict:
    repo = Path(repository).resolve()
    preflight = json.loads(Path(preflight_summary_json).read_text(encoding="utf-8"))
    if preflight.get("promotion_preflight") != "HOLD" or preflight.get("promotion_blocker") != "DIRTY_WORKTREE_REQUIRES_EXPLICIT_CURATION":
        raise ValueError("Phase 6.35 expected the Phase 6.34 dirty-worktree curation hold")
    candidates: set[Path] = set()
    for root_name in ("src", "database", "tests", "docs", "config", "scripts"):
        root = repo / root_name
        if root.is_dir():
            candidates.update(path for path in root.rglob("*") if path.is_file())
    candidates.update(repo / name for name in ROOT_METADATA if (repo / name).is_file())
    candidates.update(path for pattern in ("*.md", "*.txt", "*.cmd", "*.bat") for path in repo.glob(pattern) if path.is_file())
    rows = []
    for path in sorted(candidates, key=lambda item: item.as_posix().lower()):
        relative = path.relative_to(repo).as_posix()
        decision, reason = classify_curation_path(relative)
        rows.append({"path": relative, "decision": decision, "reason": reason, "size_bytes": path.stat().st_size, "sha256": _hash(path)})
    inventory = pd.DataFrame(rows)
    output_path = Path(output_csv)
    summary_path = Path(summary_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(output_path, index=False, encoding="utf-8-sig")
    counts = inventory["decision"].value_counts().to_dict()
    summary = {
        "phase": "V3.2.1 Phase 6.35",
        "curation_status": "PLAN_READY",
        "repository": str(repo),
        "source_preflight": str(preflight_summary_json),
        "files_inventory_total": len(inventory),
        "decision_counts": {key: int(value) for key, value in counts.items()},
        "manifest_sha256": _hash(output_path),
        "explicit_operator_approval_required": True,
        "files_staged": 0,
        "files_deleted": 0,
        "git_commit_created": False,
        "git_tag_created": False,
        "output_csv": str(output_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"summary_json": str(summary_path)}
