"""Apply timestamped formatters to uvicorn log handlers."""
from __future__ import annotations

import logging

_ACCESS_LOG_FMT = "%(asctime)s %(levelname)s:     %(message)s"
_ACCESS_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def apply_uvicorn_log_timestamps() -> None:
    formatter = logging.Formatter(fmt=_ACCESS_LOG_FMT, datefmt=_ACCESS_LOG_DATEFMT)
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(logger_name).handlers:
            handler.setFormatter(formatter)
