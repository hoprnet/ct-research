from dataclasses import dataclass, field

from .base_classes import ExplicitParams


@dataclass(init=False, repr=False)
class HostParams(ExplicitParams):
    url: str = field(metadata={"env": "HOPRD_API_HOST"})
    token: str = field(metadata={"env": "HOPRD_API_TOKEN"})
