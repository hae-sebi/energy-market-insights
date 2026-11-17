import pytest

from emi import __version__
from emi.cli import main


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Run CLI tests in an empty directory without EMI_* / API key variables."""
    monkeypatch.chdir(tmp_path)
    for var in ("EMI_DB_PATH", "EMI_LOG_LEVEL", "EMI_ASSISTANT_ENABLED", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert main([]) == 1
    assert "usage: emi" in capsys.readouterr().out


def test_config_masks_secret(capsys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-123")
    assert main(["config"]) == 0
    out = capsys.readouterr().out
    assert "sk-secret-123" not in out
    assert "anthropic_api_key" in out
    assert "set" in out


def test_config_error_exit_code(capsys, monkeypatch):
    monkeypatch.setenv("EMI_LOG_LEVEL", "loud")
    assert main(["config"]) == 2
    assert "Configuration error" in capsys.readouterr().err
