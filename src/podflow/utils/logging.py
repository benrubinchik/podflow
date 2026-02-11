"""Logging setup using rich."""

from __future__ import annotations

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler

# Force UTF-8 on Windows to avoid encoding errors with Rich
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(force_terminal=True)

_configured = False


def setup_logging(verbose: bool = False) -> None:
    global _configured
    if _configured:
        return

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                show_path=verbose,
            )
        ],
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
