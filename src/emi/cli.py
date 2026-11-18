"""Command-line entry point (``emi``).

After ``pip install -e .`` the command ``emi`` is available in the terminal
(registered under ``[project.scripts]`` in pyproject.toml). Examples::

    emi --version
    emi config        # show the effective settings

Subcommands are added step by step (ingest, clean, train, plan, backtest, serve).
"""

from __future__ import annotations

import argparse  # Python's built-in library for parsing command-line arguments
import sys
from collections.abc import Sequence

from emi import __version__
from emi.config import ConfigError, load_settings


def _cmd_config(_args: argparse.Namespace) -> int:
    """Handler for ``emi config``: print the effective settings.

    Returns an exit code, the number a program reports back to the shell:
    0 = success, anything else = error (here 2 = invalid configuration).
    The leading underscore in ``_args`` signals "parameter intentionally unused".
    """
    try:
        settings = load_settings()
    except ConfigError as exc:
        # Error messages go to stderr (the error channel), not to normal output.
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    for key, value in settings.describe().items():
        # `{key:<18}` pads the key to 18 characters, so the values line up.
        print(f"{key:<18} {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Define which commands and options ``emi`` understands."""
    parser = argparse.ArgumentParser(
        prog="emi",
        description="Day-ahead price forecasting and load shifting based on SMARD data.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Subcommands work like `git commit` / `git push`: `emi config`, later `emi ingest`, ...
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_config = sub.add_parser("config", help="show the effective configuration (secrets masked)")
    # Remember which function handles this subcommand; main() calls it as args.func.
    p_config.set_defaults(func=_cmd_config)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its exit code.

    ``argv`` is the list of arguments, e.g. ``["config"]``. ``None`` means "use
    the real command line" (``sys.argv``). Tests pass a list directly instead
    of starting a separate process.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    # No subcommand given (just `emi`): show the help text and signal an error.
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


# This block only runs when the file is executed directly (`python -m emi.cli`),
# not when it is imported by another module or a test.
if __name__ == "__main__":
    raise SystemExit(main())
