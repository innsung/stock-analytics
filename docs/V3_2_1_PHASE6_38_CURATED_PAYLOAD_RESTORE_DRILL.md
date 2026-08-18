# V3.2.1 Phase 6.38 — Curated Payload Restore Drill

The curated RC payload is extracted into a temporary clean-room directory after archive path-safety validation. Every restored file is checked against the embedded SHA-256 and size manifest, then the complete test suite is executed from the restored tree.

The temporary directory is removed after the drill. No Git operation, deployment, or external publication occurs.
