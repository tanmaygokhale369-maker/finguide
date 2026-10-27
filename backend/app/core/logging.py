"""
Logging configuration.

Brick 03 scope: a single place that configures Python's standard logging
for the whole app — console output, level driven by settings.debug, and
a consistent format. This does not add log aggregation/shipping (that's
a Brick 20 / production-readiness concern) or request-body logging of
financial data (which Brick 19 explicitly forbids without care).
"""

import logging
import sys

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if this is called more than once (e.g. under
    # --reload, which re-imports the module in the same process in tests).
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root_logger.addHandler(handler)

    # Uvicorn's own loggers should follow the same format/level rather than
    # printing in their own style.
    for noisy_logger in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(noisy_logger).handlers = []
        logging.getLogger(noisy_logger).propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
