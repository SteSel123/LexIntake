"""Central stdlib logging for LexIntake console output."""

from __future__ import annotations

import logging
ROOT_LOGGER_NAME = "lexintake"
_FORMAT = "%(levelname)s %(name)s: %(message)s"
_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Attach one StreamHandler to the lexintake root logger."""
    global _configured
    root = logging.getLogger(ROOT_LOGGER_NAME)
    root.setLevel(level)
    if _configured or root.handlers:
        _configured = True
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_console_logger(name: str | None = None) -> logging.Logger:
    """Return a child of the shared lexintake logger (no extra handlers)."""
    configure_logging()
    if not name or name == ROOT_LOGGER_NAME:
        return logging.getLogger(ROOT_LOGGER_NAME)
    if name.startswith(f"{ROOT_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def reset_logging() -> None:
    """Remove handlers (tests)."""
    global _configured
    root = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    _configured = False
