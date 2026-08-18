# V3.2.1 Phase 6.28 — Release restore drill

The canonical Phase 6.26 release ZIP is restored into an isolated temporary directory after path-traversal checks. Every manifest artifact is revalidated by size and SHA-256, then the restored canonical ledger is parsed for 399 unique events and the restored actionable queue is confirmed empty. The temporary restore directory is automatically removed afterward.
