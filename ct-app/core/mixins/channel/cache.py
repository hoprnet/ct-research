from ...api.response_objects import Channel
from ..runtime_state import NodeRuntimeState


class ChannelCacheMixin(NodeRuntimeState):
    @property
    def address_to_open_channel(self) -> dict[str, Channel]:
        if self._cached_address_to_open_channel is None and self.channels:
            self._cached_address_to_open_channel = {
                c.destination: c
                for c in self.channels.outgoing
                if c.status.is_open and hasattr(c, "destination")
            }
        return self._cached_address_to_open_channel or {}

    def invalidate_channel_cache(self) -> None:
        self._cached_address_to_open_channel = None
