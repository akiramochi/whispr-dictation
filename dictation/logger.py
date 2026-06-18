"""Lightweight file logging to %APPDATA%/Whispr/whispr.log for diagnostics."""
from __future__ import annotations

import logging

from .config import config_dir

LOG_PATH = config_dir() / "whispr.log"


def get_logger() -> logging.Logger:
    log = logging.getLogger("whispr")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    # Truncate on each launch so the file stays small and easy to read.
    handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s",
                                            datefmt="%H:%M:%S"))
    log.addHandler(handler)
    return log
