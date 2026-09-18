# ChainC2 Sentinel — Structured Logging
"""Structured JSON logging configuration for ChainC2 Sentinel.

Uses only the Python standard library `logging` module.
Log output is JSON-formatted for machine readability in the research context.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Each log line contains: timestamp, level, logger name, message,
    and any extra fields attached to the record.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            A single-line JSON string representing the log record.
        """
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra fields added via the `extra` parameter
        for key in ("component", "event_id", "source", "event_type"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def setup_logging(
    level: str = "INFO",
    logger_name: str = "chainc2_sentinel",
) -> logging.Logger:
    """Configure structured JSON logging for ChainC2 Sentinel.

    Args:
        level: Logging level string (e.g. "DEBUG", "INFO", "WARNING").
        logger_name: Name for the logger instance.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(logger_name)

    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate output
    logger.propagate = False

    return logger
