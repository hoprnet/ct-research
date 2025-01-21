import random

from core.components import MessageFormat


def test_message_bytes():
    size = random.randint(1, 100)
    relayer = "foo"
    message = MessageFormat(relayer, size)

    assert len(message.bytes) == size
    assert message.relayer == relayer

