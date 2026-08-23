from src.cli.command_dispatcher import COMMAND_GROUPS, command_group


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
