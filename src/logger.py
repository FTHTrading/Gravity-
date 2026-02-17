"""
Structured logging setup for reproducible research auditing.
All operations are logged with timestamps and module identifiers.
"""

import logging
from src.config import LOG_FORMAT, LOG_LEVEL, LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger that writes to both console and file."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)

    return logger
