"""Application settings, read from environment variables and an optional ``.env`` file.

Secrets (the LLM API key) are only ever read from the environment / ``.env`` and are
never printed: ``repr()`` and :meth:`Settings.describe` mask them.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}

DEFAULT_DB_PATH = Path("data/emi.sqlite")
DEFAULT_LOADS_PATH = Path("config/loads.yaml")
DEFAULT_ASSISTANT_MODEL = "claude-haiku-5-5"


class ConfigError(ValueError):
    """Raised when an environment variable has an invalid value."""


def _parse_bool(name: str, raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be a boolean (true/false), got {raw!r}")


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    db_path: Path = DEFAULT_DB_PATH
    loads_path: Path = DEFAULT_LOADS_PATH
    log_level: str = "INFO"
    assistant_enabled: bool = False
    assistant_model: str = DEFAULT_ASSISTANT_MODEL
    anthropic_api_key: str | None = field(default=None, repr=False)

    @property
    def assistant_active(self) -> bool:
        """The assistant runs only if it is switched on *and* an API key is configured."""
        return self.assistant_enabled and bool(self.anthropic_api_key)

    def describe(self) -> dict[str, str]:
        """Human-readable settings with secrets masked (safe to print or log)."""
        return {
            "db_path": str(self.db_path),
            "loads_path": str(self.loads_path),
            "log_level": self.log_level,
            "assistant_enabled": str(self.assistant_enabled).lower(),
            "assistant_model": self.assistant_model,
            "anthropic_api_key": "set" if self.anthropic_api_key else "not set",
            "assistant_active": str(self.assistant_active).lower(),
        }


def load_settings(env: Mapping[str, str] | None = None, *, dotenv: bool = True) -> Settings:
    """Build :class:`Settings` from ``env`` (defaults to ``os.environ``).

    If ``dotenv`` is true and no explicit ``env`` is given, a ``.env`` file in the current
    working directory is read as well; real environment variables take precedence.
    ``os.environ`` itself is never modified.
    """
    if env is None:
        file_values: dict[str, str] = {}
        dotenv_path = Path.cwd() / ".env"
        if dotenv and dotenv_path.is_file():
            file_values = {k: v for k, v in dotenv_values(dotenv_path).items() if v is not None}
        env = {**file_values, **os.environ}

    log_level = env.get("EMI_LOG_LEVEL", "INFO").strip().upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError(f"EMI_LOG_LEVEL must be a logging level, got {log_level!r}")

    return Settings(
        db_path=Path(env.get("EMI_DB_PATH") or DEFAULT_DB_PATH),
        loads_path=Path(env.get("EMI_LOADS_PATH") or DEFAULT_LOADS_PATH),
        log_level=log_level,
        assistant_enabled=_parse_bool(
            "EMI_ASSISTANT_ENABLED", env.get("EMI_ASSISTANT_ENABLED"), default=False
        ),
        assistant_model=env.get("EMI_ASSISTANT_MODEL") or DEFAULT_ASSISTANT_MODEL,
        anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
    )
