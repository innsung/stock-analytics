from types import SimpleNamespace
import pytest
from src.cli.ml_diagnostic_commands import run_ml_diagnostic_command

def test_data_guard_error_preserves_context(monkeypatch):
    monkeypatch.setattr("src.cli.ml_diagnostic_commands.assert_persistent_data_v321",
        lambda *args: (_ for _ in ()).throw(RuntimeError("missing")))
    with pytest.raises(SystemExit, match="DATA GUARD"):
        run_ml_diagnostic_command(None, SimpleNamespace(db_path="x"), SimpleNamespace(benchmark_code="K"))
