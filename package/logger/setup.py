"""Colorized / JSON logging shared by every microservice."""
from __future__ import annotations

import logging
import sys
from typing import Optional

# ANSI — no extra dependency
_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_LEVEL = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[35m",  # magenta
}
_NAME = "\033[34m"  # blue


class ColorFormatter(logging.Formatter):
    def __init__(self, *, color: bool = True):
        super().__init__()
        self.color = color and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%H:%M:%S")
        level = record.levelname
        name = record.name
        msg = record.getMessage()
        if record.exc_info:
            msg = f"{msg}\n{self.formatException(record.exc_info)}"
        if not self.color:
            return f"{ts} {level:<8} [{name}] {msg}"
        lc = _LEVEL.get(level, "")
        return (
            f"{_DIM}{ts}{_RESET} "
            f"{lc}{_BOLD}{level:<8}{_RESET} "
            f"{_NAME}[{name}]{_RESET} {msg}"
        )


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # ponytail: minimal JSON line; upgrade to structlog if needed
        msg = record.getMessage().replace("\\", "\\\\").replace('"', '\\"')
        return (
            f'{{"ts":"{self.formatTime(record, "%Y-%m-%dT%H:%M:%S")}",'
            f'"level":"{record.levelname}","logger":"{record.name}","msg":"{msg}"}}'
        )


def setup_logging(
    level: str = "INFO",
    *,
    json_logs: bool = False,
    color: Optional[bool] = None,
) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        use_color = True if color is None else color
        handler.setFormatter(ColorFormatter(color=use_color))
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Quiet noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
