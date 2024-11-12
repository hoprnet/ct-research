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


class ApiObject:
    def __init__(self, data: dict):
        for key, value in self.keys.items():
            setattr(self, key, _convert(data.get(value, None)))

        self.post_init()

    def post_init(self):
        pass


class Addresses(ApiObject):
    keys = {"hopr": "hopr", "native": "native"}


class Balances(ApiObject):
    keys = {
        "hopr": "hopr",
        "native": "native",
        "safe_native": "safeNative",
        "safe_hopr": "safeHopr",
    }


class Infos(ApiObject):
    keys = {"hopr_node_safe": "hoprNodeSafe"}


class ConnectedPeer(ApiObject):
    keys = {"address": "peerAddress", "peer_id": "peerId", "version": "reportedVersion"}


class Channel(ApiObject):
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


class TicketPrice(ApiObject):
    keys = {"value": "price"}

    def post_init(self):
        self.value = float(self.value) / 1e18


class OpenedChannel(ApiObject):
    keys = {"channel_id": "channelId", "receipt": "transactionReceipt"}


class Channels:
    def __init__(self, data: dict):
        self.all = [Channel(channel) for channel in data.get("all", [])]
        self.incoming = []
        self.outgoing = []
