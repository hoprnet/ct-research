from core.components.messages import MessageFormat


def test_create_message():
    message = MessageFormat("random_relayer")
    assert message.relayer == "random_relayer"
    assert message.timestamp is not None
    assert isinstance(message.timestamp, int)

def test_parse_message():
    encoded = MessageFormat("random_relayer")
    decoded = MessageFormat.parse(encoded.format())

    assert decoded.relayer == encoded.relayer
    assert decoded.timestamp == encoded.timestamp

