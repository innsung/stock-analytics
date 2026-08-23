from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from types import MappingProxyType
from typing import Callable, Literal, Mapping, NamedTuple


Invocation = Literal[
    "args",
    "settings",
    "runtime",
    "event",
    "conn_settings",
    "collection",
    "portfolio",
    "conn_args",
]


class RunnerSpec(NamedTuple):
    module_name: str
    runner_name: str
    invocation: Invocation


VALID_INVOCATIONS = frozenset(Invocation.__args__)
REGISTRY_INVOCATIONS = MappingProxyType({
    "foundation": frozenset({"runtime", "event", "conn_settings"}),
    "audit": frozenset({"args", "settings"}),
    "workflow": frozenset({"args", "settings"}),
    "processing": frozenset({"args", "settings"}),
    "terminal": frozenset({"args", "conn_settings", "collection", "portfolio", "conn_args"}),
})


def _validate_runner_specs(
    raw_specs: Mapping[str, tuple[str, str, Invocation]],
    registry_name: str,
) -> Mapping[str, RunnerSpec]:
    specs = {}
    for group, raw_spec in raw_specs.items():
        spec = RunnerSpec(*raw_spec)
        if not spec.module_name or not spec.runner_name:
            raise ValueError(f"Incomplete runner spec in {registry_name}: {group}")
        if spec.invocation not in VALID_INVOCATIONS:
            raise ValueError(f"Unsupported invocation in {registry_name}: {group}={spec.invocation}")
        if spec.invocation not in REGISTRY_INVOCATIONS[registry_name]:
            raise ValueError(
                f"Invocation not allowed in {registry_name}: {group}={spec.invocation}"
            )
        specs[group] = spec
    return MappingProxyType(specs)


COMMAND_GROUPS = {
    "runtime": frozenset({
        "shadow-list", "daily-status", "ml-readiness", "shadow-report", "daily-shadow",
        "build-feature-store", "ml-train", "ml-walk-forward", "ml-predict",
    }),
    "data_operation": frozenset({
        "import-valuation-snapshots-v321", "build-data-foundation-v321", "krx-provider-check-v321",
        "acquire-historical-data-v321", "db-health-v321", "backup-db-v321",
    }),
    "event": frozenset({
        "acquire-payout-actions-v321", "build-event-reconciliation-v321", "build-total-return-v321",
        "prepare-event-verification-v321", "finalize-event-reconciliation-v321",
        "prepare-official-event-evidence-v321", "resolve-official-events-v321",
        "acquire-official-event-candidates-v321", "enrich-official-evidence-v321",
        "build-market-adjustment-evidence-v321", "merge-strict-evidence-v321",
    }),
    "dividend": frozenset({
        "build-stock-cash-amount-candidates-v321", "prepare-official-cash-events-v321",
        "validate-official-cash-events-v321", "compare-cash-amount-candidates-v321",
        "prepare-benchmark-etf-distributions-v321", "validate-benchmark-etf-distributions-v321",
        "inject-benchmark-etf-events-v321", "summarize-stock-dividend-resolution-v321",
        "acquire-kodex-distributions-v321", "build-stock-dividend-ambiguity-report-v321",
        "discover-kodex-dynamic-endpoints-v321", "refine-stock-dividend-candidates-v321",
        "rank-probe-kodex-endpoints-v321", "acquire-stock-dividend-decisions-v321",
        "build-stock-dividend-exdate-queue-v321", "inspect-kodex-high-signal-responses-v321",
        "extract-dart-dividend-record-dates-v321", "merge-dividend-date-candidates-v321",
        "build-explicit-stock-exdate-evidence-v321", "export-benchmark-calendar-v321",
        "build-record-date-calendar-candidates-v321", "parse-kodex-distribution-tables-v321",
        "build-market-exdate-verification-queue-v321", "validate-official-market-exdates-v321",
        "summarize-kodex-high-signal-bodies-v321",
    }),
}

AUDIT_COMMAND_GROUPS = {
    "kind": frozenset({"crosscheck-kind-dividends-v321", "retry-kind-dividends-v321"}),
    "company_adjustment": frozenset({"verify-samsung-heavy-rights-v321", "audit-amorepacific-restructuring-v321", "audit-overseas-listing-delistings-v321"}),
    "company_applicability": frozenset({"audit-lgchem-subsidiary-rights-v321", "audit-hdhyundai-exchangeable-bond-v321", "audit-ecoprobm-merger-transfer-v321"}),
    "merger_followup": frozenset({"audit-kakao-zero-ratio-merger-v321", "audit-celltrion-merger-followups-v321", "audit-kakao-overseas-dr-delisting-v321", "audit-samsung-heavy-preferred-delisting-warnings-v321"}),
    "subsidiary_audit": frozenset({"audit-hd-ksoe-subsidiary-zero-ratio-merger-v321", "audit-ecoprobm-subsidiary-capital-increases-v321", "audit-lgchem-historical-subsidiary-capital-v321", "audit-amorepacific-us-subsidiary-capital-v321", "audit-skhynix-subsidiary-capital-v321", "audit-cj-schwans-subsidiary-mergers-v321", "audit-kakao-games-subsidiary-capital-v321"}),
    "market_followup_audit": frozenset({"audit-naver-line-overseas-delisting-v321", "audit-historical-administrative-trading-halts-v321", "audit-related-party-rights-participation-v321"}),
    "completion_followup": frozenset({"audit-samsung-heavy-rights-price-followups-v321", "audit-asset-transfer-completion-reports-v321", "audit-physical-split-business-transfer-completions-v321"}),
    "amendment_followup": frozenset({"audit-amorepacific-attachment-followups-v321", "audit-rights-offering-followups-v321", "audit-hdhyundai-subsidiary-rights-amendments-v321"}),
    "amendment_crosscheck": frozenset({"audit-kakao-split-amendments-v321", "audit-historical-amendment-duplicates-v321", "audit-ecoprobm-rights-support-disclosures-v321"}),
    "final_company_audit": frozenset({"verify-ecoprobm-bonus-issue-v321", "audit-hd-ksoe-third-party-capital-v321", "audit-shinhan-neoplux-share-exchange-v321"}),
}

WORKFLOW_COMMAND_GROUPS = {
    "release": frozenset({
        "build-release-quality-gate-v321", "verify-release-artifact-integrity-v321", "verify-release-restore-drill-v321",
        "build-runtime-readiness-gate-v321", "build-release-candidate-seal-v321", "build-rc-promotion-readiness-v321",
        "build-release-approval-handoff-v321", "build-release-notes-v321", "build-repository-promotion-preflight-v321",
        "build-release-curation-manifest-v321", "build-manual-curation-resolution-v321", "build-curated-release-payload-v321",
        "verify-curated-payload-restore-v321", "build-final-promotion-gate-v321", "build-final-release-bundle-v321",
    }),
    "adjustment_applicability": frozenset({
        "audit-historical-merger-spinoff-applicability-v321", "reparse-celltrion-merger-v321",
        "audit-historical-capital-reductions-v321", "audit-incomplete-primary-adjustments-v321",
    }),
    "primary_adjustment": frozenset({
        "validate-primary-adjustment-market-dates-v321", "audit-historical-rights-applicability-v321",
        "extract-primary-adjustment-document-terms-v321",
    }),
    "historical_chain": frozenset({
        "consolidate-historical-legal-chains-v321", "validate-historical-chain-documents-v321",
        "quarantine-periodic-dividend-aggregates-v321", "build-historical-legal-event-chain-v321",
    }),
    "kind": frozenset({
        "parse-kind-dividends-v321", "reconcile-kind-dividends-v321",
        "acquire-kind-market-exdates-v321", "discover-kind-market-exdates-v321",
    }),
}

PROCESSING_COMMAND_GROUPS = {
    "resolution_planning": frozenset({"prioritize-resolution-gaps-v321", "build-recent-dividend-acquisition-manifest-v321", "recover-acquisition-company-names-v321"}),
    "kind_followup": frozenset({"discover-kind-market-notices-batch-v321", "acquire-paired-kind-dividend-decisions-v321", "build-paired-kind-market-observations-v321", "acquire-direct-kind-dividend-decisions-v321", "extract-kind-aggregate-market-targets-v321"}),
    "coverage_classification": frozenset({"audit-market-notice-coverage-v321", "classify-recent-corporate-actions-v321"}),
    "corporate_action_document": frozenset({"build-corporate-action-candidate-manifest-v321", "select-market-adjustment-candidates-v321", "acquire-missing-corporate-action-documents-v321", "parse-corporate-action-documents-v321", "review-complex-corporate-actions-v321"}),
    "spinoff": frozenset({"audit-listed-spinoff-valuation-v321", "build-spinoff-distribution-ledger-v321", "audit-spinoff-fractional-settlement-v321", "audit-spinoff-evidence-completeness-v321", "build-complex-action-coverage-gate-v321"}),
    "subsidiary_action": frozenset({"prioritize-current-resolution-backlog-v321", "acquire-subsidiary-action-documents-v321", "parse-subsidiary-action-applicability-v321", "integrate-not-applicable-evidence-v321", "resolve-residual-subsidiary-actions-v321", "integrate-residual-subsidiary-evidence-v321"}),
    "direct_action": frozenset({"build-direct-action-document-inventory-v321", "review-direct-action-groups-v321", "integrate-direct-action-evidence-v321", "verify-samsung-sdi-rights-v321", "integrate-strict-event-evidence-v321", "route-actionable-resolution-backlog-v321"}),
    "historical_dividend": frozenset({"build-recent-dividend-evidence-inventory-v321", "acquire-historical-dividend-decisions-v321", "parse-historical-dividend-decisions-v321", "build-historical-dividend-exdate-candidates-v321"}),
    "historical_kind": frozenset({"discover-historical-kind-exdates-v321", "build-historical-kind-strict-evidence-v321", "integrate-historical-dividend-evidence-v321", "build-residual-dividend-backlog-v321"}),
    "dividend_resolution": frozenset({"resolve-ambiguous-kind-notice-v321", "resolve-broadened-kind-notices-v321", "recover-pre-exdate-dividend-evidence-v321", "resolve-explicit-no-dividend-v321"}),
    "dividend_backlog": frozenset({"defer-non-pit-dividends-v321", "resolve-recent-followups-v321", "route-historical-backlog-v321"}),
}

TERMINAL_COMMAND_GROUPS = {
    "kodex": frozenset({"discover-kodex-next-hops-v321", "phase516-selfcheck"}),
    "ml_diagnostic": frozenset({"ml-diagnose-v321"}),
    "collection": frozenset({"collect-price", "collect-financial", "collect-multi", "collect-valuation", "collect-financial-series"}),
    "portfolio": frozenset({"rank-universe", "shadow-run", "portfolio-verify", "external-verify", "common-verify"}),
    "core": frozenset({"analyze", "backtest", "walk-forward", "robustness"}),
}

COMMAND_GROUPS = MappingProxyType(COMMAND_GROUPS)
AUDIT_COMMAND_GROUPS = MappingProxyType(AUDIT_COMMAND_GROUPS)
WORKFLOW_COMMAND_GROUPS = MappingProxyType(WORKFLOW_COMMAND_GROUPS)
PROCESSING_COMMAND_GROUPS = MappingProxyType(PROCESSING_COMMAND_GROUPS)
TERMINAL_COMMAND_GROUPS = MappingProxyType(TERMINAL_COMMAND_GROUPS)


def _build_command_index(groups, registry_name: str):
    index = {}
    for group, commands in groups.items():
        for command in commands:
            if command in index:
                raise ValueError(f"Duplicate command in {registry_name}: {command}")
            index[command] = group
    return MappingProxyType(index)


COMMAND_INDEX = _build_command_index(COMMAND_GROUPS, "foundation")
AUDIT_COMMAND_INDEX = _build_command_index(AUDIT_COMMAND_GROUPS, "audit")
WORKFLOW_COMMAND_INDEX = _build_command_index(WORKFLOW_COMMAND_GROUPS, "workflow")
PROCESSING_COMMAND_INDEX = _build_command_index(PROCESSING_COMMAND_GROUPS, "processing")
TERMINAL_COMMAND_INDEX = _build_command_index(TERMINAL_COMMAND_GROUPS, "terminal")

_all_command_index = {}
for registry_name, index in (
    ("foundation", COMMAND_INDEX),
    ("audit", AUDIT_COMMAND_INDEX),
    ("workflow", WORKFLOW_COMMAND_INDEX),
    ("processing", PROCESSING_COMMAND_INDEX),
    ("terminal", TERMINAL_COMMAND_INDEX),
):
    for command, group in index.items():
        if command in _all_command_index:
            previous_registry, _ = _all_command_index[command]
            raise ValueError(f"Command registered in both {previous_registry} and {registry_name}: {command}")
        _all_command_index[command] = (registry_name, group)
ALL_COMMAND_INDEX = MappingProxyType(_all_command_index)


AUDIT_RUNNER_SPECS = {
    "kind": ("src.cli.kind_commands", "run_kind_command", "args"),
    "company_adjustment": ("src.cli.company_adjustment_commands", "run_company_adjustment_command", "settings"),
    "company_applicability": ("src.cli.company_applicability_commands", "run_company_applicability_command", "settings"),
    "merger_followup": ("src.cli.merger_followup_commands", "run_merger_followup_command", "settings"),
    "subsidiary_audit": ("src.cli.subsidiary_audit_commands", "run_subsidiary_audit_command", "settings"),
    "market_followup_audit": ("src.cli.market_followup_audit_commands", "run_market_followup_audit_command", "settings"),
    "completion_followup": ("src.cli.completion_followup_commands", "run_completion_followup_command", "settings"),
    "amendment_followup": ("src.cli.amendment_followup_commands", "run_amendment_followup_command", "args"),
    "amendment_crosscheck": ("src.cli.amendment_crosscheck_commands", "run_amendment_crosscheck_command", "args"),
    "final_company_audit": ("src.cli.final_company_audit_commands", "run_final_company_audit_command", "settings"),
}

FOUNDATION_RUNNER_SPECS = {
    "runtime": ("src.cli.runtime_commands", "run_runtime_command", "runtime"),
    "data_operation": ("src.cli.data_operation_commands", "run_data_operation_command", "conn_settings"),
    "event": ("src.cli.event_commands", "run_event_command", "event"),
    "dividend": ("src.cli.dividend_commands", "run_dividend_command", "conn_settings"),
}

WORKFLOW_RUNNER_SPECS = {
    "release": ("src.cli.release_commands", "run_release_command", "args"),
    "adjustment_applicability": ("src.cli.adjustment_applicability_commands", "run_adjustment_applicability_command", "args"),
    "primary_adjustment": ("src.cli.primary_adjustment_commands", "run_primary_adjustment_command", "settings"),
    "historical_chain": ("src.cli.historical_chain_commands", "run_historical_chain_command", "settings"),
    "kind": ("src.cli.kind_commands", "run_kind_command", "args"),
}

PROCESSING_RUNNER_SPECS = {
    "resolution_planning": ("src.cli.resolution_planning_commands", "run_resolution_planning_command", "args"),
    "kind_followup": ("src.cli.kind_followup_commands", "run_kind_followup_command", "args"),
    "coverage_classification": ("src.cli.coverage_classification_commands", "run_coverage_classification_command", "args"),
    "corporate_action_document": ("src.cli.corporate_action_document_commands", "run_corporate_action_document_command", "settings"),
    "spinoff": ("src.cli.spinoff_commands", "run_spinoff_command", "args"),
    "subsidiary_action": ("src.cli.subsidiary_action_commands", "run_subsidiary_action_command", "settings"),
    "direct_action": ("src.cli.direct_action_commands", "run_direct_action_command", "settings"),
    "historical_dividend": ("src.cli.historical_dividend_commands", "run_historical_dividend_command", "settings"),
    "historical_kind": ("src.cli.historical_kind_commands", "run_historical_kind_command", "settings"),
    "dividend_resolution": ("src.cli.dividend_resolution_commands", "run_dividend_resolution_command", "args"),
    "dividend_backlog": ("src.cli.dividend_backlog_commands", "run_dividend_backlog_command", "settings"),
}

TERMINAL_RUNNER_SPECS = {
    "kodex": ("src.cli.kodex_commands", "run_kodex_command", "args"),
    "ml_diagnostic": ("src.cli.ml_diagnostic_commands", "run_ml_diagnostic_command", "conn_settings"),
    "collection": ("src.cli.collection_commands", "run_collection_command", "collection"),
    "portfolio": ("src.cli.portfolio_commands", "run_portfolio_command", "portfolio"),
    "core": ("src.cli.core_commands", "run_core_command", "conn_args"),
}

FOUNDATION_RUNNER_SPECS = _validate_runner_specs(FOUNDATION_RUNNER_SPECS, "foundation")
AUDIT_RUNNER_SPECS = _validate_runner_specs(AUDIT_RUNNER_SPECS, "audit")
WORKFLOW_RUNNER_SPECS = _validate_runner_specs(WORKFLOW_RUNNER_SPECS, "workflow")
PROCESSING_RUNNER_SPECS = _validate_runner_specs(PROCESSING_RUNNER_SPECS, "processing")
TERMINAL_RUNNER_SPECS = _validate_runner_specs(TERMINAL_RUNNER_SPECS, "terminal")


@lru_cache(maxsize=None)
def _load_runner(spec: RunnerSpec) -> tuple[Callable, Invocation]:
    return getattr(import_module(spec.module_name), spec.runner_name), spec.invocation


def _dispatch_from_spec(group, specs, settings, args) -> bool:
    if group is None:
        return False
    runner, invocation = _load_runner(specs[group])
    if invocation == "settings":
        runner(settings, args)
    else:
        runner(args)
    return True


def command_group(command: str) -> str | None:
    return COMMAND_INDEX.get(command)


def audit_command_group(command: str) -> str | None:
    return AUDIT_COMMAND_INDEX.get(command)


def workflow_command_group(command: str) -> str | None:
    return WORKFLOW_COMMAND_INDEX.get(command)


def processing_command_group(command: str) -> str | None:
    return PROCESSING_COMMAND_INDEX.get(command)


def terminal_command_group(command: str) -> str | None:
    return TERMINAL_COMMAND_INDEX.get(command)


def command_route(command: str) -> tuple[str, str] | None:
    return ALL_COMMAND_INDEX.get(command)


def command_requires_database(command: str) -> bool:
    route = command_route(command)
    if route is None:
        raise ValueError(f"Unsupported command: {command}")

    registry, group = route
    if registry == "foundation":
        return True
    if registry == "terminal":
        return TERMINAL_RUNNER_SPECS[group].invocation != "args"
    return False


def dispatch_foundation_command(
    conn,
    settings,
    args,
    *,
    resolve_codes,
    print_shadow_report,
    execute_daily_shadow,
    load_universe,
    group=None,
) -> bool:
    group = group or command_group(args.command)
    if group is None:
        return False
    runner, invocation = _load_runner(FOUNDATION_RUNNER_SPECS[group])
    if invocation == "runtime":
        runner(
            conn, settings, args, resolve_codes=resolve_codes,
            print_shadow_report=print_shadow_report, execute_daily_shadow=execute_daily_shadow,
        )
    elif invocation == "event":
        runner(conn, settings, args, load_universe=load_universe)
    else:
        runner(conn, settings, args)
    return True


def dispatch_audit_command(settings, args, *, group=None) -> bool:
    return _dispatch_from_spec(group or audit_command_group(args.command), AUDIT_RUNNER_SPECS, settings, args)


def dispatch_workflow_command(settings, args, *, group=None) -> bool:
    return _dispatch_from_spec(group or workflow_command_group(args.command), WORKFLOW_RUNNER_SPECS, settings, args)


def dispatch_processing_command(settings, args, *, group=None) -> bool:
    return _dispatch_from_spec(group or processing_command_group(args.command), PROCESSING_RUNNER_SPECS, settings, args)

def dispatch_terminal_command(
    conn,
    settings,
    args,
    *,
    resolve_codes,
    save_shadow_outputs,
    print_shadow_result,
    group=None,
) -> None:
    group = group or terminal_command_group(args.command)
    if group is None:
        raise ValueError(f"Unsupported command: {args.command}")
    runner, invocation = _load_runner(TERMINAL_RUNNER_SPECS[group])
    if invocation == "args":
        runner(args)
    elif invocation == "conn_settings":
        runner(conn, settings, args)
    elif invocation == "collection":
        runner(conn, settings, args, resolve_codes=resolve_codes)
    elif invocation == "portfolio":
        runner(
            conn, settings, args, resolve_codes=resolve_codes,
            save_shadow_outputs=save_shadow_outputs, print_shadow_result=print_shadow_result,
        )
    else:
        runner(conn, args)


def dispatch_command(
    conn,
    settings,
    args,
    *,
    resolve_codes,
    print_shadow_report,
    execute_daily_shadow,
    load_universe,
    save_shadow_outputs,
    print_shadow_result,
) -> None:
    route = command_route(args.command)
    if route is None:
        raise ValueError(f"Unsupported command: {args.command}")

    registry, group = route
    if registry == "foundation":
        dispatch_foundation_command(
            conn,
            settings,
            args,
            resolve_codes=resolve_codes,
            print_shadow_report=print_shadow_report,
            execute_daily_shadow=execute_daily_shadow,
            load_universe=load_universe,
            group=group,
        )
    elif registry == "audit":
        dispatch_audit_command(settings, args, group=group)
    elif registry == "workflow":
        dispatch_workflow_command(settings, args, group=group)
    elif registry == "processing":
        dispatch_processing_command(settings, args, group=group)
    else:
        dispatch_terminal_command(
            conn,
            settings,
            args,
            resolve_codes=resolve_codes,
            save_shadow_outputs=save_shadow_outputs,
            print_shadow_result=print_shadow_result,
            group=group,
        )
