from dataclasses import dataclass

from ..api.response_objects import Channel


@dataclass(frozen=True)
class ChannelGraphUpdate:
    channel_id: str
    channel: Channel
