from dataclasses import dataclass
from typing import Any, Union

from api_lib.objects.request import APIfield, RequestData


@dataclass
class OpenChannelBody(RequestData):
    amount: str
    destination: str


@dataclass
class FundChannelBody(RequestData):
    amount: str


@dataclass
class GetChannelsBody(RequestData):
    full_topology: bool = APIfield("fullTopology", False)
    including_closed: bool = APIfield("includingClosed", False)


@dataclass
class CloseChannelBody(RequestData):
    direction: str


@dataclass
class GetPeersBody(RequestData):
    quality: float


@dataclass
class CreateSessionBody(RequestData):
    capabilities: list[Any]
    destination: str
    target: Union[str, dict]
    listen_host: str = APIfield("listenHost")
    forward_path: list[str] = APIfield("forwardPath")
    return_path: list[str] = APIfield("returnPath")
    response_buffer: str = APIfield("responseBuffer")


@dataclass
class SessionCapabilitiesBody(RequestData):
    retransmission: bool = APIfield("Retransmission", False)
    segmentation: bool = APIfield("Segmentation", False)
    no_delay: bool = APIfield("NoDelay", True)
    no_rate_control: bool = APIfield("NoRateControl", True)


@dataclass
class SessionPathBodyRelayers(RequestData):
    relayers: list[str]


@dataclass
class SessionPathBodyHops(RequestData):
    hops: int = APIfield("Hops", 0)


@dataclass
class SessionTargetBody(RequestData):
    service: int = APIfield("Service", 0)
