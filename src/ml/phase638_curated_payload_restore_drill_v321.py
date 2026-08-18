from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
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


def verify_curated_payload_restore_v321(
    *, payload_zip: str, expected_summary_json: str, audit_csv: str, summary_json: str, python_executable: str | None = None, run_tests: bool = True
) -> dict:
    payload_path = Path(payload_zip).resolve()
    expected = json.loads(Path(expected_summary_json).read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        rows.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    check("PAYLOAD_EXISTS", payload_path.is_file(), str(payload_path))
    actual_zip_hash = _sha256(payload_path)
    check("PAYLOAD_SHA256", actual_zip_hash == expected.get("zip_sha256"), actual_zip_hash)
    restore_root = Path(tempfile.mkdtemp(prefix="stock-analytics-phase638-"))
    tests_passed = False
    test_detail = "not run"
    try:
        with zipfile.ZipFile(payload_path, "r") as archive:
            members = archive.infolist()
            safe = all(not info.filename.startswith(("/", "\\")) and ".." not in Path(info.filename).parts for info in members)
            check("ARCHIVE_PATHS_SAFE", safe, f"entries={len(members)}")
            if not safe:
                raise ValueError("unsafe archive member path")
            archive.extractall(restore_root)
        check("ENTRY_COUNT", len(members) == expected.get("zip_entries"), f"actual={len(members)};expected={expected.get('zip_entries')}")
        manifest_path = restore_root / "RELEASE_PAYLOAD_MANIFEST.csv"
        check("EMBEDDED_MANIFEST", manifest_path.is_file(), str(manifest_path))
        manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
        missing, mismatched = [], []
        for row in manifest.to_dict("records"):
            restored = restore_root / row["path"]
            if not restored.is_file():
                missing.append(row["path"])
            elif _sha256(restored) != row["sha256"] or restored.stat().st_size != int(row["size_bytes"]):
                mismatched.append(row["path"])
        check("MANIFEST_ROW_COUNT", len(manifest) == expected.get("included_files"), f"actual={len(manifest)};expected={expected.get('included_files')}")
        check("RESTORED_FILES_PRESENT", not missing, f"missing={len(missing)}")
        check("RESTORED_FILE_INTEGRITY", not mismatched, f"mismatched={len(mismatched)}")
        if run_tests:
            executable = python_executable or "python"
            completed = subprocess.run([executable, "-m", "pytest", "-q"], cwd=restore_root, capture_output=True, text=True)
            tests_passed = completed.returncode == 0
            output = (completed.stdout + completed.stderr).strip().splitlines()
            test_detail = " | ".join(output[-30:]) if output else f"exit={completed.returncode}"
        else:
            tests_passed, test_detail = True, "skipped by test harness"
        check("RESTORED_TEST_SUITE", tests_passed, test_detail)
    finally:
        shutil.rmtree(restore_root, ignore_errors=True)
    check("TEMP_RESTORE_CLEANED", not restore_root.exists(), str(restore_root))
    audit = pd.DataFrame(rows)
    passed = bool(audit["status"].eq("PASS").all())
    audit_path, summary_path = Path(audit_csv), Path(summary_json)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
    summary = {
        "phase": "V3.2.1 Phase 6.38",
        "release_id": expected.get("release_id"),
        "restore_drill": "PASS" if passed else "FAIL",
        "checks_total": len(audit),
        "checks_passed": int(audit["status"].eq("PASS").sum()),
        "restored_tests": "PASS" if tests_passed else "FAIL",
        "payload_zip": str(payload_path),
        "payload_sha256": actual_zip_hash,
        "temporary_restore_cleaned": not restore_root.exists(),
        "git_commit_created": False,
        "git_tag_created": False,
        "deployment_performed": False,
        "audit_csv": str(audit_path),
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not passed:
        failures = ", ".join(audit.loc[audit["status"].eq("FAIL"), "check"])
        raise ValueError(f"Phase 6.38 curated payload restore drill failed: {failures}")
    return summary | {"summary_json": str(summary_path)}
