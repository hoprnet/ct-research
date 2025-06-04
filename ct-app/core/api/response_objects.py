from dataclasses import dataclass, field, fields
from typing import Any, Optional

from core.components.balance import Balance
from core.components.conversions import convert_unit

from .channelstatus import ChannelStatus

SURB_SIZE: int = 400
ZERO_XDAI: Balance = Balance.zero("xDai")
ZERO_WXHOPR: Balance = Balance.zero("wxHOPR")


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
            setattr(self, f.name, convert_unit(v))
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


@dataclass(init=False)
class Addresses(ApiResponseObject):
    native: str = field(default="", metadata={"path": "native"})


@dataclass(init=False)
class Balances(ApiResponseObject):
    hopr: Balance = field(default_factory=ZERO_WXHOPR, metadata={"path": "hopr"})
    native: Balance = field(default_factory=ZERO_XDAI, metadata={"path": "native"})
    safe_native: Balance = field(default_factory=ZERO_XDAI, metadata={"path": "safeNative"})
    safe_hopr: Balance = field(default_factory=ZERO_WXHOPR, metadata={"path": "safeHopr"})


@dataclass(init=False)
class Infos(ApiResponseObject):
    hopr_node_safe: str = field(default="", metadata={"path": "hoprNodeSafe"})

    def post_init(self):
        self.hopr_node_safe = try_to_lower(self.hopr_node_safe)


@dataclass(init=False)
class ConnectedPeer(ApiResponseObject):
    address: str = field(default="", metadata={"path": "address"})
    multiaddr: str = field(default="", metadata={"path": "multiaddr"})
    version: str = field(default="", metadata={"path": "reportedVersion"})

    def post_init(self):
        self.address = try_to_lower(self.address)


@dataclass(init=False)
class Channel(ApiResponseObject):
    balance: Balance = field(default_factory=ZERO_WXHOPR, metadata={"path": "balance"})
    id: str = field(default="", metadata={"path": "channelId"})
    destination: str = field(default="", metadata={"path": "destination"})
    source: str = field(default="", metadata={"path": "source"})
    status: Optional[ChannelStatus] = field(default=None, metadata={"path": "status"})

    def post_init(self):
        self.status = ChannelStatus.fromString(self.status)
        self.destination = try_to_lower(self.destination)
        self.source = try_to_lower(self.source)


@dataclass(init=False)
class TicketPrice(ApiResponseObject):
    value: Balance = field(default_factory=ZERO_WXHOPR, metadata={"path": "price"})


@dataclass(init=False)
class Configuration(ApiResponseObject):
    price: Balance = field(
        default_factory=ZERO_WXHOPR, metadata={"path": "hopr/protocol/outgoing_ticket_price"}
    )


@dataclass(init=False)
class OpenedChannel(ApiResponseObject):
    channel_id: str = field(default="", metadata={"path": "channelId"})
    receipt: str = field(default="", metadata={"path": "transactionReceipt"})


class Channels:
    def __init__(self, data: dict):
        self.all = [Channel(channel) for channel in data.get("all", [])]
        self.incoming = []
        self.outgoing = []

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self)


@dataclass(init=False)
class Session(ApiResponseObject):
    ip: str = field(default="", metadata={"path": "ip"})
    port: int = field(default=0, metadata={"path": "port"})
    protocol: str = field(default="", metadata={"path": "protocol"})
    target: str = field(default="", metadata={"path": "target"})
    mtu: int = field(default=0, metadata={"path": "mtu"})

    def post_init(self):
        self.payload = self.mtu - SURB_SIZE

    @property
    def as_path(self):
        return f"session/{self.protocol}/{self.ip}/{self.port}"


@dataclass(init=False)
class SessionFailure(ApiResponseObject):
    status: str = field(default="", metadata={"path": "status"})
    error: str = field(default="", metadata={"path": "error"})
