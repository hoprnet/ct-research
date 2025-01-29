import random

import pytest

from core.components import MessageFormat


@pytest.mark.parametrize("size",[(random.randint(10, 100))])
def test_message_bytes(size: int):
    relayer = "foo"
    message = MessageFormat(relayer, size)

    assert len(message.bytes) == size
    assert message.relayer == relayer

