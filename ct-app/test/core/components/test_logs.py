import logging
from io import StringIO

from core.components.logs import JSONFormatter, configure_logging


def reset_logging_state():
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.setLevel(logging.NOTSET)
    logging.getLogger("core.api").setLevel(logging.NOTSET)
    logging.getLogger("core.mixins").setLevel(logging.NOTSET)
    logging.getLogger("core.mixins.session").setLevel(logging.NOTSET)
    logging.getLogger("core.mixins.peers").setLevel(logging.NOTSET)


def test_configure_logging_sets_global_debug_level(monkeypatch):
    reset_logging_state()
    monkeypatch.setenv("LOG_LEVEL", "debug")

    configure_logging()

    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger("core.api").getEffectiveLevel() == logging.DEBUG
    assert logging.getLogger("core.mixins.session").getEffectiveLevel() == logging.DEBUG


def test_configure_logging_supports_per_library_overrides(monkeypatch):
    reset_logging_state()
    logging.getLogger("core.api")
    logging.getLogger("core.mixins.session")
    logging.getLogger("core.mixins.peers")
    monkeypatch.setenv("LOG_LEVEL", "info,core.api=debug,mixins=warning")

    configure_logging()

    assert logging.getLogger().level == logging.INFO
    assert logging.getLogger("core.api").level == logging.DEBUG
    assert logging.getLogger("core.mixins").level == logging.WARNING
    assert logging.getLogger("core.mixins.session").getEffectiveLevel() == logging.WARNING
    assert logging.getLogger("core.mixins.peers").getEffectiveLevel() == logging.WARNING


def test_configure_logging_reuses_existing_handler(monkeypatch):
    reset_logging_state()
    monkeypatch.setenv("LOG_LEVEL", "info")

    configure_logging()
    configure_logging()

    root_logger = logging.getLogger()
    named_handlers = [handler for handler in root_logger.handlers if getattr(handler, "name", None)]
    assert [handler.name for handler in named_handlers].count("ct-json-stderr") == 1


def test_configure_logging_honors_log_enabled_false(monkeypatch):
    reset_logging_state()
    monkeypatch.setenv("LOG_ENABLED", "false")

    configure_logging()

    assert logging.getLogger().disabled is True


def test_json_formatter_uses_get_message_for_dict_args():
    stream = StringIO()
    handler = logging.StreamHandler(stream=stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("test.core.components.logs.formatter")
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info("hello", {"k": "v"})
    output = stream.getvalue()
    assert '"message": "hello"' in output
