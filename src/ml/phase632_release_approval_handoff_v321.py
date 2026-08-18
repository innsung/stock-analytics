from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release_approval_handoff_v321(
    *,
    rc_manifest_json: str,
    readiness_summary_json: str,
    readiness_audit_csv: str,
    handoff_json: str,
    checklist_md: str,
) -> dict:
    """Build a deterministic operator handoff without promoting or tagging the RC."""
    manifest_path = Path(rc_manifest_json)
    readiness_path = Path(readiness_summary_json)
    audit_path = Path(readiness_audit_csv)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    audit = pd.read_csv(audit_path, dtype=str).fillna("")

    checks = {
        "release_id_consistent": manifest.get("release_id") == readiness.get("release_id") == "V3.2.1-RC1",
        "seal_passed": manifest.get("seal_status") == "PASS",
        "promotion_ready": readiness.get("promotion_state") == "PROMOTION_READY",
        "readiness_checks_complete": readiness.get("checks_total") == readiness.get("checks_passed") == 12,
        "readiness_audit_all_pass": len(audit) == 12 and bool(audit["status"].eq("PASS").all()),
        "actionable_queue_empty": manifest.get("ledger", {}).get("actionable_rows") == 0,
        "no_implicit_repository_mutation": not manifest.get("git_tag_created") and not readiness.get("git_commit_created") and not readiness.get("git_tag_created"),
    }
    status = "READY_FOR_OPERATOR_APPROVAL" if all(checks.values()) else "HOLD"
    payload = {
        "phase": "V3.2.1 Phase 6.32",
        "release_id": "V3.2.1-RC1",
        "handoff_status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks_total": len(checks),
        "checks_passed": int(sum(checks.values())),
        "checks": {key: "PASS" if value else "FAIL" for key, value in checks.items()},
        "source_evidence": {
            "rc_manifest": {"path": str(manifest_path), "sha256": _sha256(manifest_path)},
            "readiness_summary": {"path": str(readiness_path), "sha256": _sha256(readiness_path)},
            "readiness_audit": {"path": str(audit_path), "sha256": _sha256(audit_path)},
        },
        "ledger": manifest.get("ledger"),
        "operator_actions_required": [
            "Review the dirty worktree and curate intended release files.",
            "Run the full test suite in the curated tree.",
            "Create the release commit and annotated tag only after explicit approval.",
            "Verify the final distribution archive hash after promotion.",
        ],
        "git_commit_created": False,
        "git_tag_created": False,
        "deployment_performed": False,
        "fail_closed": True,
    }
    handoff_path = Path(handoff_json)
    checklist_path = Path(checklist_md)
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    checklist_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    checklist_path.write_text(
        "# V3.2.1-RC1 Release Approval Checklist\n\n"
        f"Handoff status: `{status}` ({payload['checks_passed']}/{payload['checks_total']} checks passed)\n\n"
        "- [ ] Review and curate the current dirty worktree.\n"
        "- [ ] Re-run the complete test suite in the curated tree.\n"
        "- [ ] Confirm the three unresolved rows remain intentionally routed (2 deferred, 1 blocked).\n"
        "- [ ] Approve and create the release commit.\n"
        "- [ ] Approve and create the annotated release tag.\n"
        "- [ ] Verify the promoted distribution archive SHA-256.\n\n"
        "No commit, tag, deployment, or external publication was performed by Phase 6.32.\n",
        encoding="utf-8",
    )
    if status == "HOLD":
        failed = ", ".join(key for key, value in checks.items() if not value)
        raise ValueError(f"Phase 6.32 release approval handoff failed: {failed}")
    return payload | {"handoff_json": str(handoff_path), "checklist_md": str(checklist_path)}
