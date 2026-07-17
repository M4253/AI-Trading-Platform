"""Structured logs that deliberately omit request bodies and secrets."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        for field in ('event', 'request_id', 'method', 'status_code', 'exception_type'):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, sort_keys=True, default=str)


def configure_structured_logging() -> None:
    """Configure a dedicated application logger without changing host logging."""
    logger = logging.getLogger('ai_trading_platform')
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def app_logger() -> logging.Logger:
    return logging.getLogger('ai_trading_platform')
