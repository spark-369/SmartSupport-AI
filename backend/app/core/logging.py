"""Application logging configuration (stdlib logging, single formatter)."""

from __future__ import annotations

import logging
import sys

_configured = False

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATEFMT = "%H:%M:%S"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logging once and return the app logger."""
    global _configured
    root = logging.getLogger()
    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
        root.handlers = [handler]
        root.setLevel(level.upper())
        # Third-party noise reduction.
        for noisy in ("httpx", "httpcore", "asyncio", "celery.utils.log"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        _configured = True
    else:
        root.setLevel(level.upper())
    return logging.getLogger("smartsupport")


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``smartsupport`` namespace."""
    return logging.getLogger(f"smartsupport.{name}")
