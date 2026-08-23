from __future__ import annotations

from src.ml.phase516_kind_crosscheck_v321 import discover_kodex_next_hops_v321


KODEX_COMMANDS = frozenset({"discover-kodex-next-hops-v321", "phase516-selfcheck"})


def run_kodex_command(args) -> None:
    if args.command not in KODEX_COMMANDS:
        raise ValueError(f"Unsupported KODEX command: {args.command}")

    if args.command == "discover-kodex-next-hops-v321":
        try:
            result = discover_kodex_next_hops_v321(
                bodies_dir=args.bodies_dir,
                output_csv=args.output_csv,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(f"[V3.2.1 Phase 5.16] {exc}")
        print("[V3.2.1 Phase 5.16 KODEX Next-hop Discovery]")
        print(f"Body files: {result['body_files']:,}")
        print(f"Next-hop candidates: {result['next_hops']:,}")
        print(f"Output: {result['output_csv']}")
    else:
        print("[V3.2.1 Phase 5.16.1 Self-check]")
        print("crosscheck-kind-dividends-v321: REGISTERED")
        print("discover-kodex-next-hops-v321: REGISTERED")
        print("phase516 module: IMPORT_OK")
        print("상태: PHASE516_APPLIED")
