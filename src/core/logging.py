"""Centralized logging configuration for the RAG knowledge base.

Provides ``setup_logging()`` to configure the stdlib logger hierarchy based on
the ``RAG_LOG_LEVEL`` environment variable (via ``settings.LOG_LEVEL``).  Also
exports ``is_debug_enabled()`` so other modules can guard expensive log calls.

Call ``setup_logging()`` once at application startup — it is safe to call
multiple times (idempotent).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from core.settings import settings

# Loggers that should be set to DEBUG when RAG_LOG_LEVEL=DEBUG.
_DEBUG_LOGGERS: tuple[str, ...] = (
    "mcp_server",
    "retrieval",
    "llm",
    "graph",
    "document_processing",
)


def setup_logging(**kwargs: Any) -> None:
    """Configure project-wide logging based on current settings.

    Parameters
    ----------
    **kwargs : Any
        Extra keyword arguments passed to
        ``logging.basicConfig()`` (e.g. ``force=True``).

    This function is idempotent — calling it multiple times will not duplicate
    handlers or change the level after the first invocation.
    """
    level_name = str(settings.LOG_LEVEL).upper()
    try:
        level = getattr(logging, level_name, logging.INFO)
    except AttributeError:
        level = logging.INFO

    # Guard against re-configuration when handlers are already attached.
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    kwargs.setdefault("format", "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s")
    kwargs.setdefault("stream", sys.stdout)
    kwargs.setdefault("level", level)

    logging.basicConfig(**kwargs)

    # When DEBUG is requested, explicitly set all project sub-loggers to DEBUG
    # so that even nested packages emit debug-level messages.
    if settings.LOG_LEVEL.upper() == "DEBUG":
        for logger_name in _DEBUG_LOGGERS:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)


def is_debug_enabled() -> bool:
    """Return ``True`` if the current log level is DEBUG."""
    return str(settings.LOG_LEVEL).upper() == "DEBUG"
