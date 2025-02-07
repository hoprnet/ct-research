from core.components.messages import MessageFormat

relayer = "12D3KooWPq6mC6uewNRANc4YRcigkP1bEUKUFkLX2fBB6deP32Z7s"
def test_create_message():
    message = MessageFormat(relayer)

    assert message.relayer == relayer
    assert message.timestamp is not None
    assert isinstance(message.timestamp, int)
    assert message.index == 0

def test_parse_message():
    encoded = MessageFormat(relayer)
    decoded = MessageFormat.parse(encoded.format())

    assert decoded.relayer == encoded.relayer
    assert decoded.timestamp == encoded.timestamp
    assert decoded.index == encoded.index

def test_message_byte_size():
    MessageFormat.index = MessageFormat.range - 1
    message = MessageFormat(relayer)
    
    bytes = message.bytes()
    assert len(bytes) < 462

def test_increase_message_index():
    MessageFormat.index = 0
    messages = [MessageFormat(relayer) for _ in range(20)]
    assert all([message.index == i for i, message in enumerate(messages)])

def test_loop_message_index():
    MessageFormat.index = 0
    MessageFormat.range = 5
    messages = [MessageFormat(relayer) for _ in range(MessageFormat.range+1)]
    indexes = [message.index for message in messages]
    assert indexes == list(range(MessageFormat.range)) + [0]


