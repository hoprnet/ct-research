from ..types.message_format import MessageFormat
from ..types.peer import Peer


class RelayPacer:
    def __init__(self) -> None:
        self._last_sent_at = dict[str, float]()

    def due_messages(
        self,
        peers: dict[str, Peer],
        minimum_delay_between_batches: float,
        now: float,
    ) -> list[MessageFormat]:
        current_relayers = set(peers.keys())
        for stale_relayer in list(self._last_sent_at.keys()):
            if stale_relayer not in current_relayers:
                self._last_sent_at.pop(stale_relayer, None)

        due = list[MessageFormat]()
        for peer in peers.values():
            if peer.yearly_message_count is None:
                self._last_sent_at.pop(peer.address.native, None)
                continue

            delay = peer.message_delay
            if delay is None:
                continue

            message = peer.build_relay_request(delay, minimum_delay_between_batches)
            send_interval = delay * message.batch_size
            last_sent_at = self._last_sent_at.get(peer.address.native)
            if last_sent_at is not None and now - last_sent_at < send_interval:
                continue

            due.append(message)
            self._last_sent_at[peer.address.native] = now

        return due
