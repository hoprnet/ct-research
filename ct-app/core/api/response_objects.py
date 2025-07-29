from dataclasses import dataclass, field, fields
from decimal import Decimal
from typing import Any

from core.components.balance import Balance

from .channelstatus import ChannelStatus

SURB_SIZE: int = 400


def try_to_lower(value: Any):
    if isinstance(value, str):
        return value.lower()
    return value


class ApiResponseObject:
    def __init__(self, data: dict):
        for f in fields(self):
            path = f.metadata.get("path", f.name)
            v = data
            for subkey in path.split("/"):
                v = v.get(subkey, None)
                if v is None:
                    break

            setattr(self, f.name, f.type(v))  # ty: ignore[call-non-callable]
        self.post_init()

    def post_init(self):
        pass

    @property
    def is_null(self):
        return all(getattr(self, key) is None for key in [f.name for f in fields(self)])

    @property
    def as_dict(self) -> dict:
        return {key: getattr(self, key) for key in [f.name for f in fields(self)]}

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return all(
            getattr(self, key) == getattr(other, key) for key in [f.name for f in fields(self)]
        )


class ApiMetricResponseObject(ApiResponseObject):
    def __init__(self, data: str):
        self.data = data.split("\n")

        for f in fields(self):
            values = {}
            labels = f.metadata.get("labels", [])

            for line in self.data:
                if not line.startswith(f.name):
                    continue

                value = line.split(" ")[-1]

                if len(labels) == 0:
                    setattr(self, f.name, f.type(value))  # ty: ignore[call-non-callable]
                else:
                    labels_values = {
                        pair.split("=")[0].strip('"'): pair.split("=")[1].strip('"')
                        for pair in line.split("{")[1].split("}")[0].split(",")
                    }

                    dict_path = [labels_values[label] for label in labels]
                    current = values

                    for part in dict_path[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    if dict_path[-1] not in current:
                        current[dict_path[-1]] = Decimal("0")
                    current[dict_path[-1]] += Decimal(value)

            if len(labels) > 0:
                setattr(self, f.name, f.type(values))  # ty: ignore[call-non-callable]


@dataclass(init=False)
class Addresses(ApiResponseObject):
    native: str = field()


@dataclass(init=False)
class Balances(ApiResponseObject):
    hopr: Balance = field()
    native: Balance = field()
    safe_native: Balance = field(metadata={"path": "safeNative"})
    safe_hopr: Balance = field(metadata={"path": "safeHopr"})


@dataclass(init=False)
class Infos(ApiResponseObject):
    hopr_node_safe: str = field(metadata={"path": "hoprNodeSafe"})

    def post_init(self):
        self.hopr_node_safe = try_to_lower(self.hopr_node_safe)


@dataclass(init=False)
class ConnectedPeer(ApiResponseObject):
    address: str = field()
    multiaddr: str = field()

    def post_init(self):
        self.address = try_to_lower(self.address)


@dataclass(init=False)
class Channel(ApiResponseObject):
    balance: Balance = field()
    id: str = field(metadata={"path": "channelId"})
    destination: str = field()
    source: str = field()
    status: ChannelStatus = field()

    def post_init(self):
        self.destination = try_to_lower(self.destination)
        self.source = try_to_lower(self.source)


@dataclass(init=False)
class TicketPrice(ApiResponseObject):
    value: Balance = field(metadata={"path": "price"})


@dataclass(init=False)
class Configuration(ApiResponseObject):
    price: Balance = field(metadata={"path": "hopr/protocol/outgoing_ticket_price"})


@dataclass(init=False)
class OpenedChannel(ApiResponseObject):
    channel_id: str = field(metadata={"path": "channelId"})
    receipt: str = field(default="", metadata={"path": "transactionReceipt"})


@dataclass(init=False)
class Metrics(ApiMetricResponseObject):
    hopr_tickets_incoming_statistics: dict = field(metadata={"labels": ["statistic"]})
    hopr_packets_count: dict = field(metadata={"labels": ["type"]})


class Channels:
    def __init__(self, data: dict):
        self.all = [Channel(c) for c in data.get("all", [])]
        self.incoming = [Channel(c) for c in data.get("incoming", [])]
        self.outgoing = [Channel(c) for c in data.get("outgoing", [])]

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self)


@dataclass(init=False)
class Session(ApiResponseObject):
    ip: str = field()
    port: int = field()
    protocol: str = field()
    target: str = field()
    mtu: int = field()

    @property
    def payload(self):
        return 2*(self.mtu - SURB_SIZE)

    @property
    def as_path(self):
        return f"session/{self.protocol}/{self.ip}/{self.port}"


@dataclass(init=False)
class SessionFailure(ApiResponseObject):
    status: str = field(metadata={"path": "status"})
    error: str = field(metadata={"path": "error"})
