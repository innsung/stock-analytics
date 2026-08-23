from types import SimpleNamespace
import pytest
from src.cli.resolution_planning_commands import run_resolution_planning_command

def test_unknown_command_is_rejected():
    with pytest.raises(ValueError, match="Unsupported resolution-planning command"):
        run_resolution_planning_command(SimpleNamespace(command="unknown"))
