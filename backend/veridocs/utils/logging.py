"""
Structured logging module for VeriDocs with request/job context and secret redaction.
"""

import contextvars
import json
import logging
import re
import sys
from typing import Any, Dict, Optional

correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)

# Common sensitive parameter patterns to redact
SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(bearer)\s+([^\s,;]+)", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Mask any accidentally leaked tokens, keys, or passwords."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r"\1=***REDACTED***", text)
    return text


class VeriDocsLogFormatter(logging.Formatter):
    """Custom formatter that attaches correlation IDs and applies secret redaction."""

    def format(self, record: logging.LogRecord) -> str:
        cid = correlation_id_ctx.get()
        record.correlation_id = cid or "-"
        original_msg = super().format(record)
        return redact_secrets(original_msg)


def setup_logger(name: str = "veridocs", level: str = "INFO") -> logging.Logger:
    """Configures and returns the central logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [cid:%(correlation_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        custom_formatter = VeriDocsLogFormatter(
            fmt="%(asctime)s [%(levelname)s] [cid:%(correlation_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(custom_formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logger()
