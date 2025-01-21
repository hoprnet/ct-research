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


class ConnectedPeer(ApiResponseObject):
    keys = {"address": "peerAddress",
            "peer_id": "peerId", "version": "reportedVersion"}


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

        if isinstance(self.destination_address, str):
            self.destination_address = self.destination_address.lower()
        if isinstance(self.source_address, str):
            self.source_address = self.source_address.lower()

class TicketPrice(ApiResponseObject):
    keys = {"value": "price"}

    def post_init(self):
        self.value = float(self.value) / 1e18


class TicketProbability(ApiResponseObject):
    keys = {"value": "probability"}

    def post_init(self):
        self.value = float(self.value)


class Configuration(ApiResponseObject):
    keys = {"probability": "hopr/protocol/outgoing_ticket_winning_prob"}


class OpenedChannel(ApiResponseObject):
    keys = {"channel_id": "channelId", "receipt": "transactionReceipt"}


class Channels:
    def __init__(self, data: dict):
        self.all = [Channel(channel) for channel in data.get("all", [])]
        self.incoming = []
        self.outgoing = []

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self)

      
class Session(ApiResponseObject):
    keys = {
        "ip": "ip",
        "port": "port",
        "protocol": "protocol",
        "target": "target",
    }
