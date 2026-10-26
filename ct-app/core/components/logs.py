import json
import logging
import os
import sys
import time
import traceback
from typing import Any, Iterable


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + (
            ".%03dZ" % (1000 * (record.created % 1))
        )

        result: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "threadId": record.threadName,
            "log_file": record.filename,
            "log_line": record.lineno,
            "fields": {"message": record.getMessage()},
        }

        if isinstance(record.args, dict):
            for key, value in record.args.items():
                result["fields"][key] = str(value)

        if record.exc_info:
            result["full_message"] = str(
                traceback.format_exception(
                    record.exc_info[0], record.exc_info[1], record.exc_info[2]
                )
            )

        if record.levelname == "WARNING":
            result["level"] = "WARN"

        return json.dumps(result)


_HANDLER_NAME = "ct-json-stderr"


def _parse_log_level(level_name: str) -> int:
    level = getattr(logging, level_name.upper(), None)
    if isinstance(level, int):
        return level
    return logging.INFO


def _parse_log_enabled(raw_value: str | None) -> bool:
    if raw_value is None:
        return True
    return raw_value.strip().lower() not in {"0", "false", "off", "no"}


def _iter_override_specs(raw_value: str) -> tuple[int, list[tuple[str, int]]]:
    parts = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not parts:
        return logging.INFO, []

    root_level = _parse_log_level(parts[0])
    overrides: list[tuple[str, int]] = []

    for part in parts[1:]:
        if "=" not in part:
            continue
        logger_name, level_name = [item.strip() for item in part.split("=", 1)]
        if not logger_name or not level_name:
            continue
        overrides.append((logger_name, _parse_log_level(level_name)))

    return root_level, overrides


def _matching_logger_names(pattern: str, known_logger_names: Iterable[str]) -> set[str]:
    if "." in pattern:
        return {pattern}

    matches: set[str] = set()
    for logger_name in known_logger_names:
        parts = logger_name.split(".")
        if pattern not in parts:
            continue
        segment_index = parts.index(pattern)
        matches.add(".".join(parts[: segment_index + 1]))

    if not matches:
        matches.add(pattern)

    return matches


def _apply_logger_overrides(overrides: list[tuple[str, int]]) -> None:
    logger_dict = logging.root.manager.loggerDict
    known_logger_names = {
        name for name, value in logger_dict.items() if isinstance(value, logging.Logger)
    }

    for pattern, level in overrides:
        for logger_name in _matching_logger_names(pattern, known_logger_names):
            logging.getLogger(logger_name).setLevel(level)


def configure_logging():
    root_logger = logging.getLogger()
    if not _parse_log_enabled(os.environ.get("LOG_ENABLED")):
        root_logger.disabled = True
        return

    root_logger.disabled = False
    root_level, overrides = _iter_override_specs(os.environ.get("LOG_LEVEL", "INFO"))

    if not any(getattr(handler, "name", None) == _HANDLER_NAME for handler in root_logger.handlers):
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.name = _HANDLER_NAME
        handler.setFormatter(JSONFormatter())
        root_logger.addHandler(handler)

    root_logger.setLevel(root_level)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    _apply_logger_overrides(overrides)
