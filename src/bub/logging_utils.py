"""Runtime logging helpers."""

from __future__ import annotations

import inspect
import logging
import os
import sys
from logging import Handler
from typing import Literal

from loguru import logger
from rich import get_console
from rich.logging import RichHandler

LogProfile = Literal["default", "chat"]

_PROFILE_FORMATS: dict[LogProfile, str] = {
    "chat": "{level} | {extra[tape]} |{message}",
    "default": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<6} | {name}:{function}:{line} | {extra[tape]} | {message}",
}
_CONFIGURED_PROFILE: LogProfile | None = None


class InterceptHandler(logging.Handler):
    """Handler that forwards stdlib logging messages to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = "importlib" in filename and "_bootstrap" in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _build_chat_handler() -> Handler:
    return RichHandler(
        console=get_console(),
        show_level=True,
        show_time=False,
        show_path=False,
        markup=False,
        rich_tracebacks=False,
    )


def _parse_log_filter() -> tuple[str, dict[str | None, str | int | bool]]:
    """Parse BUB_LOG_FILTER env var.

    Format: "level" or "module1=level,module2=level"
    Examples:
        - "info" - global INFO level
        - "debug,bub.core=debug" - global DEBUG, bub.core at DEBUG
        - "info,bub.tape=false" - global INFO, bub.tape disabled

    Returns:
        (global_level, module_filter_dict)
    """
    filter_env = os.getenv("BUB_LOG_FILTER", "info").lower()
    parts = [p.strip() for p in filter_env.split(",")]

    filter_dict: dict[str | None, str | int | bool] = {}
    global_level = "info"

    for part in parts:
        if "=" in part:
            module, level = part.split("=", 1)
            module = module.strip()
            level = level.strip()
            if level == "false":
                filter_dict[module] = False
            else:
                filter_dict[module] = level
        else:
            global_level = part

    return global_level, filter_dict


def _setup_stdlib_intercept() -> None:
    """Forward stdlib logging to loguru."""
    root_logger = logging.getLogger()
    root_logger.addHandler(InterceptHandler())


def configure_logging(*, profile: LogProfile = "default") -> None:
    """Configure process-level logging once.

    Log levels controlled by BUB_LOG_FILTER:
    - "info" - global INFO level
    - "debug,bub.core=debug" - global INFO with bub.core at DEBUG
    - "info,bub.tape=false" - global INFO, bub.tape disabled
    """
    from bub.tape.service import current_tape

    def inject_context(record) -> None:
        record["extra"]["tape"] = current_tape()

    global _CONFIGURED_PROFILE
    if profile == _CONFIGURED_PROFILE:
        return

    global_level, module_filter = _parse_log_filter()

    logger.remove()

    if profile == "chat":
        logger.add(
            _build_chat_handler(),
            level=global_level.upper(),
            format="{message}",
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.add(
            sys.stderr,
            level=global_level.upper(),
            format=_PROFILE_FORMATS[profile],
            backtrace=False,
            diagnose=False,
            filter=module_filter,
        )
        logger.configure(patcher=inject_context)

    _setup_stdlib_intercept()

    _CONFIGURED_PROFILE = profile
