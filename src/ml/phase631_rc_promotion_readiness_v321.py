from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_rc_promotion_readiness_v321(
    *, manifest_json: str, audit_output_csv: str, summary_json: str
) -> dict:
    """Fail closed unless the sealed RC is unchanged and promotion-ready."""
    manifest_path = Path(manifest_json)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        rows.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    check("RELEASE_ID", manifest.get("release_id") == "V3.2.1-RC1", str(manifest.get("release_id")))
    check("SEAL_STATUS", manifest.get("seal_status") == "PASS", str(manifest.get("seal_status")))
    check(
        "SEAL_CHECKS_COMPLETE",
        manifest.get("checks_total") == manifest.get("checks_passed") == 9,
        f"{manifest.get('checks_passed')}/{manifest.get('checks_total')}",
    )

    for label, metadata in manifest.get("artifacts", {}).items():
        path = Path(metadata.get("path", ""))
        exists = path.is_file()
        actual_hash = _sha256(path) if exists else ""
        actual_size = path.stat().st_size if exists else 0
        ok = (
            exists
            and actual_hash == metadata.get("sha256")
            and actual_size == metadata.get("size_bytes")
        )
        check(f"SEALED_ARTIFACT_{label.upper()}", ok, f"sha256={actual_hash};size={actual_size}")

    gates = manifest.get("gates", {})
    check(
        "PREREQUISITE_GATES",
        set(gates) == {"QUALITY", "INTEGRITY", "RESTORE", "RUNTIME"}
        and all(value.get("status") == "PASS" for value in gates.values()),
        json.dumps({key: value.get("status") for key, value in gates.items()}, sort_keys=True),
    )
    ledger = manifest.get("ledger", {})
    status_counts = ledger.get("status_counts", {})
    accounted = sum(int(status_counts.get(key, 0)) for key in ("VERIFIED", "NOT_APPLICABLE", "UNRESOLVED"))
    check("LEDGER_ACCOUNTING", ledger.get("rows") == accounted == 399, f"rows={ledger.get('rows')};accounted={accounted}")
    check("ACTIONABLE_QUEUE_EMPTY", ledger.get("actionable_rows") == 0, f"actionable={ledger.get('actionable_rows')}")
    residual = int(ledger.get("deferred_rows", -1)) + int(ledger.get("blocked_rows", -1))
    check(
        "RESIDUALS_TERMINALLY_ROUTED",
        residual == int(status_counts.get("UNRESOLVED", -2)) == 3,
        f"deferred={ledger.get('deferred_rows')};blocked={ledger.get('blocked_rows')};unresolved={status_counts.get('UNRESOLVED')}",
    )
    check("NO_IMPLICIT_GIT_TAG", manifest.get("git_tag_created") is False, str(manifest.get("git_tag_created")))

    audit = pd.DataFrame(rows)
    promotion_ready = bool(audit["status"].eq("PASS").all())
    audit_path = Path(audit_output_csv)
    summary_path = Path(summary_json)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    summary = {
        "phase": "V3.2.1 Phase 6.31",
        "release_id": manifest.get("release_id"),
        "promotion_readiness": "PASS" if promotion_ready else "FAIL",
        "promotion_state": "PROMOTION_READY" if promotion_ready else "HOLD",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks_total": len(audit),
        "checks_passed": int(audit["status"].eq("PASS").sum()),
        "artifact_level_only": True,
        "git_commit_created": False,
        "git_tag_created": False,
        "source_manifest": str(manifest_path),
        "audit_output_csv": str(audit_path),
        "fail_closed": True,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not promotion_ready:
        failures = ", ".join(audit.loc[audit["status"].eq("FAIL"), "check"])
        raise ValueError(f"Phase 6.31 RC promotion readiness failed: {failures}")
    return summary | {"summary_json": str(summary_path)}
