from __future__ import annotations

import os
import subprocess

from src.ml.phase626_release_quality_gate_v321 import build_release_quality_gate_v321
from src.ml.phase627_release_artifact_integrity_v321 import verify_release_artifact_integrity_v321
from src.ml.phase628_release_restore_drill_v321 import verify_release_restore_drill_v321
from src.ml.phase629_runtime_readiness_gate_v321 import build_runtime_readiness_gate_v321
from src.ml.phase630_release_candidate_seal_v321 import build_release_candidate_seal_v321
from src.ml.phase631_rc_promotion_readiness_v321 import build_rc_promotion_readiness_v321
from src.ml.phase632_release_approval_handoff_v321 import build_release_approval_handoff_v321
from src.ml.phase633_release_notes_v321 import build_release_notes_v321
from src.ml.phase634_repository_promotion_preflight_v321 import build_repository_promotion_preflight_v321
from src.ml.phase635_release_curation_manifest_v321 import build_release_curation_manifest_v321
from src.ml.phase636_manual_curation_resolution_v321 import build_manual_curation_resolution_v321
from src.ml.phase637_curated_release_payload_v321 import build_curated_release_payload_v321
from src.ml.phase638_curated_payload_restore_drill_v321 import verify_curated_payload_restore_v321
from src.ml.phase639_final_promotion_gate_v321 import build_final_promotion_gate_v321
from src.ml.phase640_final_release_bundle_v321 import build_final_release_bundle_v321


RELEASE_COMMANDS = frozenset({
    "build-release-quality-gate-v321",
    "verify-release-artifact-integrity-v321",
    "verify-release-restore-drill-v321",
    "build-runtime-readiness-gate-v321",
    "build-release-candidate-seal-v321",
    "build-rc-promotion-readiness-v321",
    "build-release-approval-handoff-v321",
    "build-release-notes-v321",
    "build-repository-promotion-preflight-v321",
    "build-release-curation-manifest-v321",
    "build-manual-curation-resolution-v321",
    "build-curated-release-payload-v321",
    "verify-curated-payload-restore-v321",
    "build-final-promotion-gate-v321",
    "build-final-release-bundle-v321",
})


def run_release_command(args) -> None:
    """Run V3.2.1 release quality, approval, and packaging commands."""
    if args.command not in RELEASE_COMMANDS:
        raise ValueError(f"지원하지 않는 릴리스 명령입니다: {args.command}")

    if args.command == "build-release-quality-gate-v321":
        try:
            result=build_release_quality_gate_v321(verification_csv=args.verification_csv,actionable_csv=args.actionable_csv,deferred_csv=args.deferred_csv,blocked_csv=args.blocked_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.26] {exc}")
        print("[V3.2.1 Phase 6.26 Release Quality Gate]");print(f"Gate: {result['release_gate']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Ledger rows: {result['input_rows']:,}");print(f"Actionable: {result['actionable_rows']:,}");print(f"Output: {result['audit_output_csv']}")
    elif args.command == "verify-release-artifact-integrity-v321":
        try:
            result=verify_release_artifact_integrity_v321(manifest_csv=args.manifest_csv,gate_summary_json=args.gate_summary_json,release_zip=args.release_zip,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.27] {exc}")
        print("[V3.2.1 Phase 6.27 Release Artifact Integrity]");print(f"Integrity: {result['integrity_status']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Manifest files: {result['manifest_files']}");print(f"ZIP entries: {result['release_zip_entries']}");print(f"Output: {result['audit_output_csv']}")
    elif args.command == "verify-release-restore-drill-v321":
        try:
            result=verify_release_restore_drill_v321(release_zip=args.release_zip,manifest_csv=args.manifest_csv,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.28] {exc}")
        print("[V3.2.1 Phase 6.28 Release Restore Drill]");print(f"Restore drill: {result['restore_drill']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Restored entries: {result['restored_entries']}");print(f"Temporary cleaned: {result['temporary_restore_cleaned']}");print(f"Output: {result['audit_output_csv']}")
    elif args.command == "build-runtime-readiness-gate-v321":
        try:
            result=build_runtime_readiness_gate_v321(requirements_lock=args.requirements_lock,main_py=args.main_py,quality_summary_json=args.quality_summary_json,integrity_summary_json=args.integrity_summary_json,restore_summary_json=args.restore_summary_json,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.29] {exc}")
        print("[V3.2.1 Phase 6.29 Runtime Readiness Gate]");print(f"Runtime: {result['runtime_readiness']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Python: {result['python_version']}");print(f"Locked dependencies: {result['locked_dependencies']}");print(f"Output: {result['audit_output_csv']}")
    elif args.command == "build-release-candidate-seal-v321":
        try:
            result=build_release_candidate_seal_v321(verification_csv=args.verification_csv,release_zip=args.release_zip,requirements_txt=args.requirements_txt,requirements_lock=args.requirements_lock,quality_summary_json=args.quality_summary_json,integrity_summary_json=args.integrity_summary_json,restore_summary_json=args.restore_summary_json,runtime_summary_json=args.runtime_summary_json,audit_output_csv=args.audit_output_csv,manifest_output_json=args.manifest_output_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.30] {exc}")
        print("[V3.2.1 Phase 6.30 Release Candidate Seal]");print(f"Release: {result['release_id']}");print(f"Seal: {result['seal_status']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Git tag created: {result['git_tag_created']}");print(f"Output: {result['manifest_output_json']}")
    elif args.command == "build-rc-promotion-readiness-v321":
        try:
            result=build_rc_promotion_readiness_v321(manifest_json=args.manifest_json,audit_output_csv=args.audit_output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.31] {exc}")
        print("[V3.2.1 Phase 6.31 RC Promotion Readiness]");print(f"Release: {result['release_id']}");print(f"State: {result['promotion_state']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Git tag created: {result['git_tag_created']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-release-approval-handoff-v321":
        try:
            result=build_release_approval_handoff_v321(rc_manifest_json=args.rc_manifest_json,readiness_summary_json=args.readiness_summary_json,readiness_audit_csv=args.readiness_audit_csv,handoff_json=args.handoff_json,checklist_md=args.checklist_md)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.32] {exc}")
        print("[V3.2.1 Phase 6.32 Release Approval Handoff]");print(f"Release: {result['release_id']}");print(f"Status: {result['handoff_status']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Git tag created: {result['git_tag_created']}");print(f"Output: {result['handoff_json']}")
    elif args.command == "build-release-notes-v321":
        try:
            result=build_release_notes_v321(handoff_json=args.handoff_json,release_notes_md=args.release_notes_md,release_record_json=args.release_record_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.33] {exc}")
        print("[V3.2.1 Phase 6.33 Release Notes]");print(f"Release: {result['release_id']}");print(f"Status: {result['release_notes_status']}");print(f"Approval: {result['approval_state']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Output: {result['release_record_json']}")
    elif args.command == "build-repository-promotion-preflight-v321":
        try:
            result=build_repository_promotion_preflight_v321(repository=args.repository,inventory_csv=args.inventory_csv,summary_json=args.summary_json)
        except (FileNotFoundError,subprocess.CalledProcessError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.34] {exc}")
        print("[V3.2.1 Phase 6.34 Repository Promotion Preflight]");print(f"Branch: {result['branch']}@{result['head']}");print(f"Status: {result['promotion_preflight']}");print(f"Changed paths: {result['changed_paths']}");print(f"Git tag created: {result['git_tag_created']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-release-curation-manifest-v321":
        try:
            result=build_release_curation_manifest_v321(repository=args.repository,preflight_summary_json=args.preflight_summary_json,output_csv=args.output_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.35] {exc}")
        print("[V3.2.1 Phase 6.35 Release Curation Manifest]");print(f"Status: {result['curation_status']}");print(f"Files: {result['files_inventory_total']}");print(f"Decisions: {result['decision_counts']}");print(f"Files staged: {result['files_staged']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-manual-curation-resolution-v321":
        try:
            result=build_manual_curation_resolution_v321(repository=args.repository,curation_manifest_csv=args.curation_manifest_csv,output_csv=args.output_csv,audit_csv=args.audit_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.36] {exc}")
        print("[V3.2.1 Phase 6.36 Manual Curation Resolution]");print(f"Status: {result['curation_resolution']}");print(f"Resolved: {result['resolved_manual_review']}/{result['input_manual_review']}");print(f"Remaining: {result['remaining_manual_review']}");print(f"Files deleted: {result['files_deleted']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-curated-release-payload-v321":
        try:
            result=build_curated_release_payload_v321(repository=args.repository,resolution_summary_json=args.resolution_summary_json,payload_zip=args.payload_zip,manifest_csv=args.manifest_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.37] {exc}")
        print("[V3.2.1 Phase 6.37 Curated Release Payload]");print(f"Release: {result['release_id']}");print(f"Status: {result['payload_status']}");print(f"Included: {result['included_files']}");print(f"Excluded: {result['excluded_files']}");print(f"SHA-256: {result['zip_sha256']}");print(f"Output: {result['payload_zip']}")
    elif args.command == "verify-curated-payload-restore-v321":
        try:
            result=verify_curated_payload_restore_v321(payload_zip=args.payload_zip,expected_summary_json=args.expected_summary_json,audit_csv=args.audit_csv,summary_json=args.summary_json,python_executable=os.sys.executable)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.38] {exc}")
        print("[V3.2.1 Phase 6.38 Curated Payload Restore Drill]");print(f"Release: {result['release_id']}");print(f"Status: {result['restore_drill']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Restored tests: {result['restored_tests']}");print(f"Temporary restore cleaned: {result['temporary_restore_cleaned']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-final-promotion-gate-v321":
        try:
            result=build_final_promotion_gate_v321(payload_summary_json=args.payload_summary_json,restore_summary_json=args.restore_summary_json,audit_csv=args.audit_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.39] {exc}")
        print("[V3.2.1 Phase 6.39 Final Promotion Gate]");print(f"Release: {result['release_id']}");print(f"Gate: {result['final_promotion_gate']}");print(f"State: {result['promotion_state']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"Output: {result['summary_json']}")
    elif args.command == "build-final-release-bundle-v321":
        try:
            result=build_final_release_bundle_v321(payload_zip=args.payload_zip,payload_summary_json=args.payload_summary_json,restore_summary_json=args.restore_summary_json,promotion_summary_json=args.promotion_summary_json,release_notes_md=args.release_notes_md,bundle_zip=args.bundle_zip,bundle_manifest_json=args.bundle_manifest_json,audit_csv=args.audit_csv,summary_json=args.summary_json)
        except (FileNotFoundError,ValueError) as exc:raise SystemExit(f"[V3.2.1 Phase 6.40] {exc}")
        print("[V3.2.1 Phase 6.40 Final Release Bundle]");print(f"Release: {result['release_id']}");print(f"Status: {result['final_bundle_status']}");print(f"State: {result['release_state']}");print(f"Checks: {result['checks_passed']}/{result['checks_total']}");print(f"SHA-256: {result['bundle_sha256']}");print(f"Output: {result['bundle_zip']}")
