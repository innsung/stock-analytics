from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_final_release_bundle_v321(
    *,
    payload_zip: str,
    payload_summary_json: str,
    restore_summary_json: str,
    promotion_summary_json: str,
    release_notes_md: str,
    bundle_zip: str,
    bundle_manifest_json: str,
    audit_csv: str,
    summary_json: str,
) -> dict:
    payload_path = Path(payload_zip)
    payload = json.loads(Path(payload_summary_json).read_text(encoding="utf-8"))
    restore = json.loads(Path(restore_summary_json).read_text(encoding="utf-8"))
    promotion = json.loads(Path(promotion_summary_json).read_text(encoding="utf-8"))
    evidence_paths = [Path(payload_summary_json), Path(restore_summary_json), Path(promotion_summary_json), Path(release_notes_md)]
    actual_payload_hash = _sha256(payload_path) if payload_path.is_file() else ""
    checks = [
        ("PAYLOAD_EXISTS", payload_path.is_file(), str(payload_path)),
        ("PAYLOAD_HASH_MATCH", actual_payload_hash == payload.get("zip_sha256"), actual_payload_hash),
        ("PAYLOAD_STATUS_PASS", payload.get("payload_status") == "PASS", str(payload.get("payload_status"))),
        ("RESTORE_STATUS_PASS", restore.get("restore_drill") == "PASS", str(restore.get("restore_drill"))),
        ("RESTORED_TESTS_PASS", restore.get("restored_tests") == "PASS", str(restore.get("restored_tests"))),
        ("PROMOTION_GATE_PASS", promotion.get("final_promotion_gate") == "PASS", str(promotion.get("final_promotion_gate"))),
        ("PROMOTION_AWAITS_APPROVAL", promotion.get("promotion_state") == "READY_AWAITING_EXPLICIT_APPROVAL", str(promotion.get("promotion_state"))),
        ("EVIDENCE_FILES_PRESENT", all(path.is_file() for path in evidence_paths), f"files={len(evidence_paths)}"),
        ("NO_IMPLICIT_RELEASE", not promotion.get("git_commit_created") and not promotion.get("git_tag_created") and not promotion.get("deployment_performed"), "commit=false;tag=false;deployment=false"),
    ]
    audit = pd.DataFrame([{"check": name, "status": "PASS" if ok else "FAIL", "detail": detail} for name, ok, detail in checks])
    passed = bool(audit["status"].eq("PASS").all())
    audit_path, manifest_path, bundle_path, summary_path = Path(audit_csv), Path(bundle_manifest_json), Path(bundle_zip), Path(summary_json)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    if not passed:
        failures = ", ".join(audit.loc[audit["status"].eq("FAIL"), "check"])
        raise ValueError(f"Phase 6.40 final release bundle preflight failed: {failures}")
    components = [payload_path, *evidence_paths, audit_path]
    manifest = {
        "phase": "V3.2.1 Phase 6.40",
        "release_id": "V3.2.1-RC1",
        "bundle_state": "SEALED_AWAITING_EXPLICIT_APPROVAL",
        "components": [{"name": path.name, "sha256": _sha256(path), "size_bytes": path.stat().st_size} for path in components],
        "git_commit_created": False,
        "git_tag_created": False,
        "deployment_performed": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in components:
            archive.write(path, arcname=path.name)
        archive.write(manifest_path, arcname="FINAL_RELEASE_BUNDLE_MANIFEST.json")
    with zipfile.ZipFile(bundle_path, "r") as archive:
        bad_entry = archive.testzip()
        entries = len(archive.infolist())
    expected_entries = len(components) + 1
    status = "PASS" if bad_entry is None and entries == expected_entries else "FAIL"
    summary = {
        "phase": "V3.2.1 Phase 6.40",
        "release_id": "V3.2.1-RC1",
        "final_bundle_status": status,
        "release_state": "SEALED_AWAITING_EXPLICIT_APPROVAL" if status == "PASS" else "HOLD",
        "checks_total": len(audit),
        "checks_passed": int(audit["status"].eq("PASS").sum()),
        "bundle_entries": entries,
        "bundle_sha256": _sha256(bundle_path),
        "bundle_size_bytes": bundle_path.stat().st_size,
        "bundle_zip": str(bundle_path),
        "bundle_manifest_json": str(manifest_path),
        "git_commit_created": False,
        "git_tag_created": False,
        "deployment_performed": False,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if status != "PASS":
        raise ValueError(f"Phase 6.40 bundle verification failed: {bad_entry}")
    return summary | {"summary_json": str(summary_path)}
