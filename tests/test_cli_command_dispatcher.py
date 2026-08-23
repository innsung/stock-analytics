from types import SimpleNamespace

import pytest

import src.cli.command_dispatcher as dispatcher
from src.cli.command_dispatcher import (
    AUDIT_COMMAND_GROUPS,
    AUDIT_RUNNER_SPECS,
    ALL_COMMAND_INDEX,
    COMMAND_GROUPS,
    FOUNDATION_RUNNER_SPECS,
    PROCESSING_COMMAND_GROUPS,
    PROCESSING_RUNNER_SPECS,
    REGISTRY_INVOCATIONS,
    CommandRequirements,
    RunnerResolutionError,
    RunnerSpec,
    TERMINAL_COMMAND_GROUPS,
    TERMINAL_RUNNER_SPECS,
    WORKFLOW_COMMAND_GROUPS,
    WORKFLOW_RUNNER_SPECS,
    _load_runner,
    _validate_runner_specs,
    audit_command_group,
    command_group,
    command_requires_database,
    command_requires_settings,
    command_requirements,
    command_route,
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
    assert command_route("build-total-return-v321") == ("foundation", "event")
    assert command_route("backtest") == ("terminal", "core")
    assert command_route("unknown-command") is None


def test_database_requirement_is_derived_from_command_route():
    assert command_requires_database("daily-shadow")
    assert command_requires_database("ml-diagnose-v321")
    assert command_requires_database("backtest")
    assert not command_requires_database("build-final-release-bundle-v321")
    assert not command_requires_database("audit-kakao-zero-ratio-merger-v321")
    assert not command_requires_database("phase516-selfcheck")

    with pytest.raises(ValueError, match="Unsupported command"):
        command_requires_database("unknown-command")


def test_settings_requirement_is_derived_from_runner_invocation():
    assert command_requires_settings("daily-shadow")
    assert command_requires_settings("audit-kakao-zero-ratio-merger-v321")
    assert command_requires_settings("backtest")
    assert not command_requires_settings("build-final-release-bundle-v321")
    assert not command_requires_settings("resolve-ambiguous-kind-notice-v321")
    assert not command_requires_settings("phase516-selfcheck")

    with pytest.raises(ValueError, match="Unsupported command"):
        command_requires_settings("unknown-command")


def test_command_requirements_describe_execution_resources_in_one_lookup():
    assert command_requirements("daily-shadow") == CommandRequirements(
        "foundation", "runtime", "runtime", True, True
    )
    assert command_requirements("build-final-release-bundle-v321") == CommandRequirements(
        "workflow", "release", "args", False, False
    )
    assert command_requirements("audit-kakao-zero-ratio-merger-v321") == CommandRequirements(
        "audit", "merger_followup", "settings", True, False
    )


def test_data_driven_runner_specs_cover_every_non_terminal_group():
    assert set(AUDIT_RUNNER_SPECS) == set(AUDIT_COMMAND_GROUPS)
    assert set(WORKFLOW_RUNNER_SPECS) == set(WORKFLOW_COMMAND_GROUPS)
    assert set(PROCESSING_RUNNER_SPECS) == set(PROCESSING_COMMAND_GROUPS)

    specs = (*AUDIT_RUNNER_SPECS.values(), *WORKFLOW_RUNNER_SPECS.values(), *PROCESSING_RUNNER_SPECS.values())
    assert all(invocation in {"args", "settings"} for _, _, invocation in specs)


def test_foundation_and_terminal_runner_specs_cover_every_group():
    assert set(FOUNDATION_RUNNER_SPECS) == set(COMMAND_GROUPS)
    assert set(TERMINAL_RUNNER_SPECS) == set(TERMINAL_COMMAND_GROUPS)

    foundation_modes = {invocation for _, _, invocation in FOUNDATION_RUNNER_SPECS.values()}
    terminal_modes = {invocation for _, _, invocation in TERMINAL_RUNNER_SPECS.values()}
    assert foundation_modes <= {"runtime", "event", "conn_settings"}
    assert terminal_modes <= {"args", "conn_settings", "collection", "portfolio", "conn_args"}


def test_all_runner_specs_are_typed_and_complete():
    registries = (
        FOUNDATION_RUNNER_SPECS,
        AUDIT_RUNNER_SPECS,
        WORKFLOW_RUNNER_SPECS,
        PROCESSING_RUNNER_SPECS,
        TERMINAL_RUNNER_SPECS,
    )
    specs = [spec for registry in registries for spec in registry.values()]

    assert all(isinstance(spec, RunnerSpec) for spec in specs)
    assert all(spec.module_name.startswith("src.cli.") for spec in specs)
    assert all(spec.runner_name.startswith("run_") for spec in specs)


def test_dispatch_indexes_and_runner_specs_are_read_only():
    with pytest.raises(TypeError):
        COMMAND_GROUPS["unexpected"] = frozenset({"unexpected-command"})

    with pytest.raises(TypeError):
        ALL_COMMAND_INDEX["unexpected-command"] = ("terminal", "core")

    with pytest.raises(TypeError):
        TERMINAL_RUNNER_SPECS["core"] = RunnerSpec(
            "src.cli.core_commands", "run_core_command", "conn_args"
        )


def test_all_runner_entrypoints_resolve_and_are_cached():
    registries = (
        FOUNDATION_RUNNER_SPECS,
        AUDIT_RUNNER_SPECS,
        WORKFLOW_RUNNER_SPECS,
        PROCESSING_RUNNER_SPECS,
        TERMINAL_RUNNER_SPECS,
    )
    specs = [spec for registry in registries for spec in registry.values()]

    _load_runner.cache_clear()
    resolved = [_load_runner(spec) for spec in specs]
    first_pass = _load_runner.cache_info()
    cached = [_load_runner(spec) for spec in specs]
    second_pass = _load_runner.cache_info()

    assert all(callable(runner) for runner, _ in resolved)
    assert cached == resolved
    assert first_pass.misses == len(set(specs))
    assert second_pass.hits - first_pass.hits == len(specs)


def test_runner_resolution_errors_identify_broken_spec(monkeypatch):
    missing_module = RunnerSpec("src.cli.missing_commands", "run_missing_command", "args")
    monkeypatch.setattr(
        dispatcher,
        "import_module",
        lambda _name: (_ for _ in ()).throw(ModuleNotFoundError("missing")),
    )
    with pytest.raises(RunnerResolutionError, match="Cannot import runner module"):
        _load_runner(missing_module)

    monkeypatch.setattr(dispatcher, "import_module", lambda _name: SimpleNamespace(not_runner=1))
    missing_function = RunnerSpec("src.cli.fake_commands", "run_fake_command", "args")
    with pytest.raises(RunnerResolutionError, match="Runner run_fake_command not found"):
        _load_runner(missing_function)

    monkeypatch.setattr(
        dispatcher,
        "import_module",
        lambda _name: SimpleNamespace(run_fake_command="not callable"),
    )
    with pytest.raises(RunnerResolutionError, match="is not callable"):
        _load_runner(missing_function)


def test_registry_invocation_contracts_are_read_only_and_enforced():
    with pytest.raises(TypeError):
        REGISTRY_INVOCATIONS["audit"] = frozenset({"runtime"})

    with pytest.raises(ValueError, match="Invocation not allowed in audit"):
        _validate_runner_specs(
            {"broken": ("src.cli.runtime_commands", "run_runtime_command", "runtime")},
            "audit",
        )


@pytest.mark.parametrize(
    ("command", "expected"),
    (
        ("daily-shadow", "foundation"),
        ("audit-kakao-zero-ratio-merger-v321", "audit"),
        ("build-final-release-bundle-v321", "workflow"),
        ("route-historical-backlog-v321", "processing"),
        ("backtest", "terminal"),
    ),
)
def test_unified_dispatch_uses_global_command_route(monkeypatch, command, expected):
    calls = []
    for registry in ("foundation", "audit", "workflow", "processing", "terminal"):
        monkeypatch.setattr(
            dispatcher,
            f"dispatch_{registry}_command",
            lambda *args, _registry=registry, **kwargs: calls.append(_registry),
        )

    dispatcher.dispatch_command(
        None,
        None,
        SimpleNamespace(command=command),
        resolve_codes=None,
        print_shadow_report=None,
        execute_daily_shadow=None,
        load_universe=None,
        save_shadow_outputs=None,
        print_shadow_result=None,
    )

    assert calls == [expected]
