from ..api.response_objects import Channel
from ..types.network_models import ChannelGraphUpdate
from .snapshot_generations import SnapshotGenerations


class ChannelGraphStore:
    """
    Non-closed channels of the network, keyed by channel id, built from the Blokli channel graph
    subscription. `sweep()` drops the channels the latest connection's snapshot did not resend.
    """

    def __init__(self):
        self._channels: dict[str, Channel] = {}
        self._generations = SnapshotGenerations[str]()

    def start_generation(self) -> None:
        self._generations.start()

    def apply(self, update: ChannelGraphUpdate) -> None:
        if update.channel.status.is_closed:
            self._channels.pop(update.channel_id, None)
            self._generations.forget(update.channel_id)
            return
        self._channels[update.channel_id] = update.channel
        self._generations.touch(update.channel_id)

    def sweep(self) -> int:
        stale = self._generations.pop_stale()
        for channel_id in stale:
            self._channels.pop(channel_id, None)
        return len(stale)

    def channels(self) -> list[Channel]:
        return list(self._channels.values())

    def __len__(self) -> int:
        return len(self._channels)
