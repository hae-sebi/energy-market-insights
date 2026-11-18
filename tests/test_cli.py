"""Tests for the ``emi`` command line. ``main()`` is called directly with a list
of arguments, exactly as if they had been typed in the terminal."""

import pytest

from emi import __version__
from emi.cli import main


# A fixture with autouse=True runs automatically before every test in this file.
# `monkeypatch` changes things only for the duration of one test and undoes
# them afterwards; `tmp_path` is a fresh empty folder.
@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Run CLI tests in an empty directory without EMI_* / API key variables."""
    monkeypatch.chdir(tmp_path)  # so no real .env file from the project is read
    for var in ("EMI_DB_PATH", "EMI_LOG_LEVEL", "EMI_ASSISTANT_ENABLED", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)


# `capsys` is a fixture that captures everything printed to stdout/stderr.
def test_version(capsys):
    # argparse ends the program after printing the version (SystemExit with code 0).
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert main([]) == 1
    assert "usage: emi" in capsys.readouterr().out


def test_config_masks_secret(capsys, monkeypatch):
    """`emi config` shows that a key is set, but never the key itself."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-123")
    assert main(["config"]) == 0
    out = capsys.readouterr().out
    assert "sk-secret-123" not in out
    assert "anthropic_api_key" in out
    assert "set" in out


def test_config_error_exit_code(capsys, monkeypatch):
    """An invalid setting leads to exit code 2 and a message on stderr."""
    monkeypatch.setenv("EMI_LOG_LEVEL", "loud")
    assert main(["config"]) == 2
    assert "Configuration error" in capsys.readouterr().err
