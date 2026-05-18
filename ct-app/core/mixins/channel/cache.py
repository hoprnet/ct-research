from ...api.response_objects import Channel
from ..runtime_state import NodeRuntimeState


class ChannelCacheMixin(NodeRuntimeState):
    @property
    def outgoing_open_channels(self) -> list[Channel]:
        if self._cached_outgoing_open is None and self.channels:
            self._cached_outgoing_open = [c for c in self.channels.outgoing if c.status.is_open]
        return self._cached_outgoing_open or []

    @property
    def incoming_open_channels(self) -> list[Channel]:
        if self._cached_incoming_open is None and self.channels:
            self._cached_incoming_open = [c for c in self.channels.incoming if c.status.is_open]
        return self._cached_incoming_open or []

    @property
    def outgoing_pending_channels(self) -> list[Channel]:
        if self._cached_outgoing_pending is None and self.channels:
            self._cached_outgoing_pending = [
                c for c in self.channels.outgoing if c.status.is_pending
            ]
        return self._cached_outgoing_pending or []

    @property
    def outgoing_not_closed_channels(self) -> list[Channel]:
        if self._cached_outgoing_not_closed is None and self.channels:
            self._cached_outgoing_not_closed = [
                c for c in self.channels.outgoing if not c.status.is_closed
            ]
        return self._cached_outgoing_not_closed or []

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
        self._cached_outgoing_open = None
        self._cached_incoming_open = None
        self._cached_outgoing_pending = None
        self._cached_outgoing_not_closed = None
        self._cached_address_to_open_channel = None
