from ..api.response_objects import Channel
from ..types.network_models import ChannelGraphUpdate


class ChannelGraphStore:
    """
    Non-closed channels of the network, keyed by channel id, built from the Blokli channel graph
    subscription.

    Each (re)connection resends a full snapshot but never mentions channels that closed while
    disconnected. Every connection therefore starts a new generation; once its snapshot has been
    received, `sweep()` drops the channels it did not resend.
    """

    def __init__(self):
        self._channels: dict[str, Channel] = {}
        self._generation_of: dict[str, int] = {}
        self._generation = 0

    def start_generation(self) -> None:
        self._generation += 1

    def apply(self, update: ChannelGraphUpdate) -> None:
        if update.channel.status.is_closed:
            self._channels.pop(update.channel_id, None)
            self._generation_of.pop(update.channel_id, None)
            return
        self._channels[update.channel_id] = update.channel
        self._generation_of[update.channel_id] = self._generation

    def sweep(self) -> int:
        stale = [cid for cid, gen in self._generation_of.items() if gen < self._generation]
        for channel_id in stale:
            self._channels.pop(channel_id, None)
            self._generation_of.pop(channel_id, None)
        return len(stale)

    def channels(self) -> list[Channel]:
        return list(self._channels.values())

    def __len__(self) -> int:
        return len(self._channels)
