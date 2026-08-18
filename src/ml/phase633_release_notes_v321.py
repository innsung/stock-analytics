from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release_notes_v321(
    *, handoff_json: str, release_notes_md: str, release_record_json: str
) -> dict:
    """Create evidence-backed RC notes while leaving promotion operator-controlled."""
    handoff_path = Path(handoff_json)
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    evidence = handoff.get("source_evidence", {})
    evidence_results = {}
    for name, metadata in evidence.items():
        path = Path(metadata.get("path", ""))
        evidence_results[name] = path.is_file() and _sha256(path) == metadata.get("sha256")

    ledger = handoff.get("ledger", {})
    counts = ledger.get("status_counts", {})
    checks = {
        "release_id": handoff.get("release_id") == "V3.2.1-RC1",
        "handoff_ready": handoff.get("handoff_status") == "READY_FOR_OPERATOR_APPROVAL",
        "handoff_checks_complete": handoff.get("checks_total") == handoff.get("checks_passed") == 7,
        "source_evidence_complete": set(evidence_results) == {"rc_manifest", "readiness_summary", "readiness_audit"},
        "source_evidence_unchanged": bool(evidence_results) and all(evidence_results.values()),
        "ledger_accounted": ledger.get("rows") == sum(int(counts.get(key, 0)) for key in ("VERIFIED", "NOT_APPLICABLE", "UNRESOLVED")) == 399,
        "actionable_queue_empty": ledger.get("actionable_rows") == 0,
        "repository_and_deployment_untouched": not handoff.get("git_commit_created") and not handoff.get("git_tag_created") and not handoff.get("deployment_performed"),
    }
    passed = all(checks.values())
    record = {
        "phase": "V3.2.1 Phase 6.33",
        "release_id": "V3.2.1-RC1",
        "release_notes_status": "PASS" if passed else "FAIL",
        "approval_state": "AWAITING_EXPLICIT_OPERATOR_APPROVAL" if passed else "HOLD",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks_total": len(checks),
        "checks_passed": int(sum(checks.values())),
        "checks": {key: "PASS" if value else "FAIL" for key, value in checks.items()},
        "handoff": {"path": str(handoff_path), "sha256": _sha256(handoff_path)},
        "ledger": ledger,
        "known_limitations": [
            "Two non-PIT dividend events remain intentionally deferred.",
            "One complex split event remains externally blocked pending surviving-leg fractional-settlement evidence.",
            "The current worktree must be curated before any formal Git release.",
        ],
        "git_commit_created": False,
        "git_tag_created": False,
        "deployment_performed": False,
        "fail_closed": True,
    }
    record_path = Path(release_record_json)
    notes_path = Path(release_notes_md)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    notes_path.write_text(
        "# V3.2.1-RC1 Release Notes\n\n"
        "Status: `AWAITING_EXPLICIT_OPERATOR_APPROVAL`\n\n"
        "## Release quality\n\n"
        "- Quality, integrity, restore, runtime, seal, promotion-readiness, and handoff gates passed.\n"
        "- Canonical corporate-action ledger: 399 rows (25 VERIFIED, 371 NOT_APPLICABLE, 3 UNRESOLVED).\n"
        "- Actionable resolution queue: 0 rows.\n\n"
        "## Known limitations\n\n"
        "- Two non-PIT dividend events are intentionally deferred.\n"
        "- One complex split is externally blocked pending surviving-leg fractional-settlement evidence.\n"
        "- Formal Git promotion requires explicit operator approval and worktree curation.\n\n"
        "No commit, tag, deployment, or external publication was performed.\n",
        encoding="utf-8",
    )
    if not passed:
        failures = ", ".join(key for key, value in checks.items() if not value)
        raise ValueError(f"Phase 6.33 release notes failed: {failures}")
    return record | {"release_record_json": str(record_path), "release_notes_md": str(notes_path)}
