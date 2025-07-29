from typing import Any

from .channelstatus import ChannelStatus


def _convert(value: Any):
    if value is None:
        return None

    try:
        value = float(value)
    except ValueError:
        pass

    try:
        integer = int(value)
        if integer == value:
            value = integer

    except ValueError:
        pass

    return value


def try_to_lower(value: Any):
    if isinstance(value, str):
        return value.lower()
    return value


class ApiResponseObject:
    def __init__(self, data: dict):
        for key, value in self.keys.items():
            v = data
            for subkey in value.split("/"):
                v = v.get(subkey, None)
                if v is None:
                    continue

            setattr(self, key, _convert(v))

        self.post_init()

    def post_init(self):
        pass

    @property
    def is_null(self):
        return all(getattr(self, key) is None for key in self.keys.keys())

    @property
    def as_dict(self) -> dict:
        return {key: getattr(self, key) for key in self.keys.keys()}

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return all(
            getattr(self, key) == getattr(other, key) for key in self.keys.keys()
        )


class Addresses(ApiResponseObject):
    keys = {"hopr": "hopr", "native": "native"}


class Balances(ApiResponseObject):
    keys = {
        "hopr": "hopr",
        "native": "native",
        "safe_native": "safeNative",
        "safe_hopr": "safeHopr",
    }


class Infos(ApiResponseObject):
    keys = {"hopr_node_safe": "hoprNodeSafe"}

    def post_init(self):
        self.hopr_node_safe = try_to_lower(self.hopr_node_safe)


class ConnectedPeer(ApiResponseObject):
    keys = {"address": "peerAddress", "peer_id": "peerId", "version": "reportedVersion"}

    def post_init(self):
        self.address = try_to_lower(self.address)


class Channel(ApiResponseObject):
    keys = {
        "balance": "balance",
        "id": "channelId",
        "destination_address": "destinationAddress",
        "destination_peer_id": "destinationPeerId",
        "source_address": "sourceAddress",
        "source_peer_id": "sourcePeerId",
        "status": "status",
    }

    def post_init(self):
        self.status = ChannelStatus.fromString(self.status)

        self.destination_address = try_to_lower(self.destination_address)
        self.source_address = try_to_lower(self.source_address)


class TicketPrice(ApiResponseObject):
    keys = {"value": "price"}

    def post_init(self):
        try:
            self.value = float(self.value) / 1e18
        except (ValueError, TypeError):
            self.value = None


class Configuration(ApiResponseObject):
    keys = {"price": "hopr/protocol/outgoing_ticket_price"}

    def post_init(self):
        if isinstance(self.price, str):
            self.price = float(self.price.split()[0])


class OpenedChannel(ApiResponseObject):
    keys = {"channel_id": "channelId", "receipt": "transactionReceipt"}


class Message(ApiResponseObject):
    keys = {"body": "body", "timestamp": "receivedAt"}


class SendMessageAck(ApiResponseObject):
    keys = {"timestamp": "timestamp"}


class Channels:
    def __init__(self, data: dict):
        self.all = [Channel(channel) for channel in data.get("all", [])]
        self.incoming = []
        self.outgoing = []

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self)
