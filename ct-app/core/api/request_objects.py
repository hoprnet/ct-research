from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Union


def api_field(api_key: Optional[str] = None, default: Optional[Any] = None, **kwargs):
    metadata = kwargs.pop("metadata", {})
    if api_key is not None:
        metadata["api_key"] = api_key

    if default is None:
        return field(metadata=metadata, **kwargs)
    else:
        return field(default=default, metadata=metadata, **kwargs)


class ApiRequestObject:
    @property
    def as_dict(self) -> dict:
        result = {}
        for f in fields(self):
            api_key = f.metadata.get("api_key", f.name)
            result[api_key] = getattr(self, f.name)
        return result

    @property
    def as_header_string(self) -> str:
        return "&".join([f"{k}={str(v).lower()}" for k, v in self.as_dict.items()])


@dataclass
class OpenChannelBody(ApiRequestObject):
    amount: str = api_field()
    destination: str = api_field()


@dataclass
class FundChannelBody(ApiRequestObject):
    amount: str = api_field()


@dataclass
class GetChannelsBody(ApiRequestObject):
    full_topology: bool = api_field("fullTopology", False)
    including_closed: bool = api_field("includingClosed", False)


@dataclass
class GetPeersBody(ApiRequestObject):
    quality: float = api_field()


@dataclass
class CreateSessionBody(ApiRequestObject):
    capabilities: List[Any] = api_field()
    destination: str = api_field()
    listen_host: str = api_field("listenHost")
    forward_path: Union[str, Dict] = api_field("forwardPath")
    return_path: Union[str, Dict] = api_field("returnPath")
    response_buffer: str = api_field("responseBuffer")
    target: Union[str, Dict] = api_field()


@dataclass
class SessionCapabilitiesBody(ApiRequestObject):
    retransmission: bool = api_field("Retransmission", False)
    segmentation: bool = api_field("Segmentation", False)
    no_delay: bool = api_field("NoDelay", True)
    no_rate_control: bool = api_field("NoRateControl", True)

    @property
    def as_array(self) -> list:
        return [f.metadata["api_key"] for f in fields(self) if getattr(self, f.name)]


@dataclass
class SessionPathBodyRelayers(ApiRequestObject):
    relayers: List[str] = api_field("IntermediatePath")


@dataclass
class SessionTargetBody(ApiRequestObject):
    service: int = api_field("Service", 0)
