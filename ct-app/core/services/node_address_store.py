from typing import Optional

from .snapshot_generations import SnapshotGenerations


class NodeAddressStore:
    """
    Public IP of each node, keyed by native address, built from the Blokli node-address
    subscription. `sweep()` drops the nodes the latest connection's snapshot did not resend,
    mirroring `ChannelGraphStore`.
    """

    def __init__(self):
        self._ips: dict[str, str] = {}
        self._generations = SnapshotGenerations[str]()

    def start_generation(self) -> None:
        self._generations.start()

    def apply(self, address: str, ip: str) -> None:
        self._ips[address] = ip
        self._generations.touch(address)

    def sweep(self) -> int:
        stale = self._generations.pop_stale()
        for address in stale:
            self._ips.pop(address, None)
        return len(stale)

    def ip_for(self, address: str) -> Optional[str]:
        return self._ips.get(address)

    def __len__(self) -> int:
        return len(self._ips)
