from typing import Any

from core.components.conversions import convert_unit

from .channelstatus import ChannelStatus

SURB_SIZE = 400


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

            setattr(self, key, convert_unit(v))

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
        return all(getattr(self, key) == getattr(other, key) for key in self.keys.keys())


class Addresses(ApiResponseObject):
    keys = {"native": "native"}


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
    keys = {"address": "address", "multiaddr": "multiaddr", "version": "reportedVersion"}

    def post_init(self):
        self.address = try_to_lower(self.address)


class Channel(ApiResponseObject):
    keys = {
        "balance": "balance",
        "id": "channelId",
        "destination": "destination",
        "source": "source",
        "status": "status",
    }

    def post_init(self):
        self.status = ChannelStatus.fromString(self.status)

        self.destination = try_to_lower(self.destination)
        self.source = try_to_lower(self.source)


class TicketPrice(ApiResponseObject):
    keys = {"value": "price"}


class Configuration(ApiResponseObject):
    keys = {"price": "hopr/protocol/outgoing_ticket_price"}

    def post_init(self):
        if isinstance(self.price, str):
            self.price = float(self.price.split()[0])


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
        "mtu": "mtu",
        "surb_size": "surbSize",
    }

    def post_init(self):
        self.payload = self.mtu - SURB_SIZE


class SessionFailure(ApiResponseObject):
    keys = {"status": "status", "error": "error"}
