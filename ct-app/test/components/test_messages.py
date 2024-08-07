from datetime import datetime

from core.components import MessageFormat


def test_message_parse():
    relayer = "Alice"
    timestamp = datetime.now()

    message = MessageFormat.parse(f"{relayer} at {timestamp}")

    assert message.relayer == relayer
    assert message.timestamp == timestamp


def test_message_format():
    relayer = "Alice"
    timestamp = datetime.now()

    message = MessageFormat(relayer, timestamp).format()

    assert relayer in message
    assert str(timestamp) in message
    assert message == f"{relayer} at {timestamp}"


def test_message_format_full_loop():
    relayer = "Alice"
    timestamp = datetime.now()

    format = MessageFormat.parse(MessageFormat(relayer, timestamp).format())

    assert relayer == format.relayer
    assert timestamp == format.timestamp
