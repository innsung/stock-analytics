from src.cli.command_dispatcher import (
    AUDIT_COMMAND_GROUPS,
    AUDIT_RUNNER_SPECS,
    ALL_COMMAND_INDEX,
    COMMAND_GROUPS,
    PROCESSING_COMMAND_GROUPS,
    PROCESSING_RUNNER_SPECS,
    TERMINAL_COMMAND_GROUPS,
    WORKFLOW_COMMAND_GROUPS,
    WORKFLOW_RUNNER_SPECS,
    audit_command_group,
    command_group,
    processing_command_group,
    terminal_command_group,
    workflow_command_group,
)


def test_foundation_dispatch_registry_has_unique_commands():
    commands = [command for group in COMMAND_GROUPS.values() for command in group]

    assert len(commands) == 51
    assert len(commands) == len(set(commands))


def test_foundation_dispatch_registry_routes_representative_commands():
    assert command_group("daily-shadow") == "runtime"
    assert command_group("backup-db-v321") == "data_operation"
    assert command_group("build-total-return-v321") == "event"
    assert command_group("validate-official-market-exdates-v321") == "dividend"
    assert command_group("unknown-command") is None


def test_audit_dispatch_registry_has_unique_commands_and_routes_groups():
    commands = [command for group in AUDIT_COMMAND_GROUPS.values() for command in group]

    assert len(commands) == 34
    assert len(commands) == len(set(commands))
    assert audit_command_group("retry-kind-dividends-v321") == "kind"
    assert audit_command_group("audit-kakao-zero-ratio-merger-v321") == "merger_followup"
    assert audit_command_group("audit-shinhan-neoplux-share-exchange-v321") == "final_company_audit"
    assert audit_command_group("unknown-command") is None


def test_workflow_dispatch_registry_has_unique_commands_and_routes_groups():
    commands = [command for group in WORKFLOW_COMMAND_GROUPS.values() for command in group]

    assert len(commands) == 30
    assert len(commands) == len(set(commands))
    assert workflow_command_group("build-final-release-bundle-v321") == "release"
    assert workflow_command_group("extract-primary-adjustment-document-terms-v321") == "primary_adjustment"
    assert workflow_command_group("build-historical-legal-event-chain-v321") == "historical_chain"
    assert workflow_command_group("parse-kind-dividends-v321") == "kind"
    assert workflow_command_group("unknown-command") is None


def test_processing_dispatch_registry_has_unique_commands_and_routes_groups():
    commands = [command for group in PROCESSING_COMMAND_GROUPS.values() for command in group]

    assert len(commands) == 47
    assert len(commands) == len(set(commands))
    assert processing_command_group("prioritize-resolution-gaps-v321") == "resolution_planning"
    assert processing_command_group("review-complex-corporate-actions-v321") == "corporate_action_document"
    assert processing_command_group("build-residual-dividend-backlog-v321") == "historical_kind"
    assert processing_command_group("route-historical-backlog-v321") == "dividend_backlog"
    assert processing_command_group("unknown-command") is None


def test_terminal_dispatch_registry_has_unique_commands_and_routes_groups():
    commands = [command for group in TERMINAL_COMMAND_GROUPS.values() for command in group]

    assert len(commands) == 17
    assert len(commands) == len(set(commands))
    assert terminal_command_group("phase516-selfcheck") == "kodex"
    assert terminal_command_group("ml-diagnose-v321") == "ml_diagnostic"
    assert terminal_command_group("collect-price") == "collection"
    assert terminal_command_group("shadow-run") == "portfolio"
    assert terminal_command_group("backtest") == "core"
    assert terminal_command_group("unknown-command") is None


def test_all_dispatch_registries_are_globally_unique_and_complete():
    registries = (
        COMMAND_GROUPS,
        AUDIT_COMMAND_GROUPS,
        WORKFLOW_COMMAND_GROUPS,
        PROCESSING_COMMAND_GROUPS,
        TERMINAL_COMMAND_GROUPS,
    )
    commands = [command for registry in registries for group in registry.values() for command in group]

    assert len(commands) == 179
    assert len(ALL_COMMAND_INDEX) == 179
    assert len(set(commands)) == 179
    assert ALL_COMMAND_INDEX["build-total-return-v321"] == ("foundation", "event")
    assert ALL_COMMAND_INDEX["backtest"] == ("terminal", "core")


def test_data_driven_runner_specs_cover_every_non_terminal_group():
    assert set(AUDIT_RUNNER_SPECS) == set(AUDIT_COMMAND_GROUPS)
    assert set(WORKFLOW_RUNNER_SPECS) == set(WORKFLOW_COMMAND_GROUPS)
    assert set(PROCESSING_RUNNER_SPECS) == set(PROCESSING_COMMAND_GROUPS)

    specs = (*AUDIT_RUNNER_SPECS.values(), *WORKFLOW_RUNNER_SPECS.values(), *PROCESSING_RUNNER_SPECS.values())
    assert all(invocation in {"args", "settings"} for _, _, invocation in specs)
