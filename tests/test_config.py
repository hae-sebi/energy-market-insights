"""Tests for reading the settings.

Most tests pass the environment as a plain dict to ``load_settings``, so they
do not depend on (or change) the real environment of the machine.
"""

import os
from pathlib import Path

import pytest

from emi.config import DEFAULT_ASSISTANT_MODEL, ConfigError, Settings, load_settings


def test_defaults_with_empty_env():
    """Nothing set -> every setting has its default value."""
    s = load_settings({})
    assert s.db_path == Path("data/emi.sqlite")
    assert s.loads_path == Path("config/loads.yaml")
    assert s.log_level == "INFO"
    assert s.assistant_enabled is False
    assert s.assistant_model == DEFAULT_ASSISTANT_MODEL
    assert s.anthropic_api_key is None
    assert s.assistant_active is False


def test_values_from_env():
    """Every variable is picked up; the log level is normalised to upper case."""
    s = load_settings(
        {
            "EMI_DB_PATH": "/tmp/x.sqlite",
            "EMI_LOADS_PATH": "my/loads.yaml",
            "EMI_LOG_LEVEL": "debug",
            "EMI_ASSISTANT_ENABLED": "true",
            "EMI_ASSISTANT_MODEL": "some-model",
            "ANTHROPIC_API_KEY": "sk-test",
        }
    )
    assert s.db_path == Path("/tmp/x.sqlite")
    assert s.loads_path == Path("my/loads.yaml")
    assert s.log_level == "DEBUG"
    assert s.assistant_model == "some-model"
    assert s.assistant_active is True


# `parametrize` runs the same test several times, once per row of inputs.
@pytest.mark.parametrize(
    ("enabled", "key", "active"),
    [
        ("true", None, False),  # switched on, but no key
        ("false", "sk-test", False),  # key present, but switched off
        ("true", "", False),  # empty key counts as missing
        ("1", "sk-test", True),
    ],
)
def test_assistant_requires_flag_and_key(enabled, key, active):
    env = {"EMI_ASSISTANT_ENABLED": enabled}
    if key is not None:
        env["ANTHROPIC_API_KEY"] = key
    assert load_settings(env).assistant_active is active


@pytest.mark.parametrize("raw", ["maybe", "2", "enabled"])
def test_invalid_bool_raises(raw):
    """Unclear values are rejected instead of being guessed."""
    with pytest.raises(ConfigError, match="EMI_ASSISTANT_ENABLED"):
        load_settings({"EMI_ASSISTANT_ENABLED": raw})


def test_invalid_log_level_raises():
    with pytest.raises(ConfigError, match="EMI_LOG_LEVEL"):
        load_settings({"EMI_LOG_LEVEL": "loud"})


def test_api_key_never_shown():
    """Neither printing the object nor describe() reveals the secret."""
    s = Settings(anthropic_api_key="sk-secret-123")
    assert "sk-secret-123" not in repr(s)
    assert "sk-secret-123" not in str(s.describe())
    assert s.describe()["anthropic_api_key"] == "set"


def test_dotenv_file_is_read_and_env_wins(tmp_path, monkeypatch):
    """Values come from .env, but a real environment variable overrides them."""
    (tmp_path / ".env").write_text("EMI_DB_PATH=from_dotenv.sqlite\nEMI_LOG_LEVEL=WARNING\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMI_DB_PATH", raising=False)
    monkeypatch.setenv("EMI_LOG_LEVEL", "ERROR")
    s = load_settings()
    assert s.db_path == Path("from_dotenv.sqlite")
    assert s.log_level == "ERROR"  # real environment beats .env
    assert "EMI_DB_PATH" not in os.environ  # reading .env has no side effects


def test_dotenv_can_be_disabled(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("EMI_DB_PATH=from_dotenv.sqlite\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMI_DB_PATH", raising=False)
    assert load_settings(dotenv=False).db_path == Path("data/emi.sqlite")
