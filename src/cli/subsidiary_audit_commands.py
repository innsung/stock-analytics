from __future__ import annotations

import requests

from src.dart.client import DartClient
from src.ml.phase604_hd_ksoe_subsidiary_zero_ratio_merger_v321 import audit_hd_ksoe_subsidiary_zero_ratio_merger_v321
from src.ml.phase605_ecoprobm_subsidiary_capital_increases_v321 import audit_ecoprobm_subsidiary_capital_increases_v321
from src.ml.phase606_lgchem_historical_subsidiary_capital_v321 import audit_lgchem_historical_subsidiary_capital_v321
from src.ml.phase607_amorepacific_us_subsidiary_capital_v321 import audit_amorepacific_us_subsidiary_capital_v321
from src.ml.phase608_skhynix_subsidiary_capital_v321 import audit_skhynix_subsidiary_capital_v321
from src.ml.phase609_cj_schwans_subsidiary_mergers_v321 import audit_cj_schwans_subsidiary_mergers_v321
from src.ml.phase610_kakao_games_subsidiary_capital_v321 import audit_kakao_games_subsidiary_capital_v321


COMMAND_SPECS = {
    "audit-hd-ksoe-subsidiary-zero-ratio-merger-v321": ("6.04", "HD KSOE Subsidiary Zero-ratio Merger", audit_hd_ksoe_subsidiary_zero_ratio_merger_v321),
    "audit-ecoprobm-subsidiary-capital-increases-v321": ("6.05", "Ecopro BM Subsidiary Capital Increases", audit_ecoprobm_subsidiary_capital_increases_v321),
    "audit-lgchem-historical-subsidiary-capital-v321": ("6.06", "LG Chem Historical Subsidiary Capital", audit_lgchem_historical_subsidiary_capital_v321),
    "audit-amorepacific-us-subsidiary-capital-v321": ("6.07", "Amorepacific US Subsidiary Capital", audit_amorepacific_us_subsidiary_capital_v321),
    "audit-skhynix-subsidiary-capital-v321": ("6.08", "SK hynix Subsidiary Capital", audit_skhynix_subsidiary_capital_v321),
    "audit-cj-schwans-subsidiary-mergers-v321": ("6.09", "CJ Schwan's Subsidiary Mergers", audit_cj_schwans_subsidiary_mergers_v321),
    "audit-kakao-games-subsidiary-capital-v321": ("6.10", "Kakao Games Subsidiary Capital", audit_kakao_games_subsidiary_capital_v321),
}


def run_subsidiary_audit_command(settings, args) -> None:
    if args.command not in COMMAND_SPECS:
        raise ValueError(f"Unsupported subsidiary-audit command: {args.command}")

    phase, label, handler = COMMAND_SPECS[args.command]
    try:
        result = handler(
            DartClient(settings.dart_api_key),
            actionable_queue_csv=args.actionable_queue_csv,
            disclosures_csv=args.disclosures_csv,
            documents_dir=args.documents_dir,
            evidence_output_csv=args.evidence_output_csv,
            audit_output_csv=args.audit_output_csv,
            summary_json=args.summary_json,
        )
    except (FileNotFoundError, ValueError, RuntimeError, requests.RequestException) as exc:
        raise SystemExit(f"[V3.2.1 Phase {phase}] {exc}")

    print(f"[V3.2.1 Phase {phase} {label}]")
    print(f"Targets: {result['target_rows']:,}")
    print(f"NOT_APPLICABLE evidence: {result['not_applicable_evidence_rows']:,}")
    print(f"Unresolved: {result['unresolved_rows']:,}")
    print(f"Output: {result['evidence_output_csv']}")
