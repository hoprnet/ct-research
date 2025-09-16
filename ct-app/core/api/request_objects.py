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
class GetPeersBody(RequestData):
    quality: float


@dataclass
class CreateSessionBody(RequestData):
    capabilities: list[Any]
    destination: str
    listen_host: str = APIfield("listenHost")
    forward_path: Union[str, dict] = APIfield("forwardPath")
    return_path: Union[str, dict] = APIfield("returnPath")
    response_buffer: str = APIfield("responseBuffer")
    target: Union[str, dict]


@dataclass
class SessionCapabilitiesBody(RequestData):
    retransmission: bool = APIfield("Retransmission", False)
    segmentation: bool = APIfield("Segmentation", False)
    no_delay: bool = APIfield("NoDelay", True)
    no_rate_control: bool = APIfield("NoRateControl", True)


@dataclass
class SessionPathBodyRelayers(RequestData):
    relayers: list[str] = APIfield("IntermediatePath")


@dataclass
class SessionTargetBody(RequestData):
    service: int = APIfield("Service", 0)
