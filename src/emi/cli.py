"""Command-line entry point (``emi``).

Subcommands are added step by step (ingest, clean, train, plan, backtest, serve).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from emi import __version__
from emi.config import ConfigError, load_settings


def _cmd_config(_args: argparse.Namespace) -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    for key, value in settings.describe().items():
        print(f"{key:<18} {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="emi",
        description="Day-ahead price forecasting and load shifting based on SMARD data.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_config = sub.add_parser("config", help="show the effective configuration (secrets masked)")
    p_config.set_defaults(func=_cmd_config)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
