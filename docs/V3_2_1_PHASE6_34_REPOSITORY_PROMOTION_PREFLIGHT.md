# V3.2.1 Phase 6.34 — Repository Promotion Preflight

This read-only Git preflight inventories every changed or untracked path and classifies it as a release candidate, evidence requiring review, generated output, runtime artifact, or manual-review item.

A dirty tree produces `HOLD` with `DIRTY_WORKTREE_REQUIRES_EXPLICIT_CURATION`. This is an expected safety result: the phase does not stage files, alter `.gitignore`, commit, tag, delete, or deploy anything.
