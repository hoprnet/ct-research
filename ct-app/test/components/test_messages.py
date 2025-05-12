from core.components.messages import MessageFormat

relayer = "12D3KooWPq6mC6uewNRANc4YRcigkP1bEUKUFkLX2fBB6deP32Zr"
sender = "12D3KooWJ6mC6uewNRANc4YRcigkP1bEUKUFkLX2fBB6deP32Zs"
default_size = 1000


def test_create_message():
    message = MessageFormat(default_size, relayer, multiplier=5)

    assert message.relayer == relayer
    assert message.timestamp is not None
    assert isinstance(message.timestamp, int)
    assert message.index == 0
    assert message.multiplier == 5


def test_parse_message():
    encoded = MessageFormat(default_size, relayer, sender, multiplier=10)
    decoded = MessageFormat.parse(encoded.format())

    assert decoded.relayer == encoded.relayer
    assert decoded.sender == encoded.sender
    assert decoded.timestamp == encoded.timestamp
    assert decoded.index == encoded.index
    assert decoded.multiplier == encoded.multiplier
    assert decoded.inner_index == encoded.inner_index


def test_increase_inner_index():
    encoded = MessageFormat(default_size, relayer)
    decoded = MessageFormat.parse(encoded.format())

    decoded.increase_inner_index()

    assert decoded.inner_index == encoded.inner_index + 1


def test_message_byte_size():
    MessageFormat.index = MessageFormat.range - 1
    message = MessageFormat(default_size, relayer)

    bytes = message.bytes()
    assert len(bytes) == default_size


def test_increase_message_index():
    MessageFormat.index = 0
    messages = [MessageFormat(default_size, relayer) for _ in range(20)]
    assert all([message.index == i for i, message in enumerate(messages)])


def test_loop_message_index():
    MessageFormat.index = 0
    MessageFormat.range = 5
    messages = [MessageFormat(default_size, relayer) for _ in range(MessageFormat.range + 1)]
    indexes = [message.index for message in messages]
    assert indexes == list(range(MessageFormat.range)) + [0]
