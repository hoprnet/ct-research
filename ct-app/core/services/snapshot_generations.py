from collections.abc import Hashable
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)


class SnapshotGenerations(Generic[K]):
    """
    Tracks which keys the current Blokli subscription connection has reported.

    Blokli resends a full snapshot on every (re)connection but never mentions entries that
    disappeared while disconnected. Each connection starts a new generation; keys not reported
    since then are stale once the snapshot has been received.
    """

    def __init__(self):
        self._current = 0
        self._seen: dict[K, int] = {}

    def start(self) -> None:
        self._current += 1

    def touch(self, key: K) -> None:
        self._seen[key] = self._current

    def forget(self, key: K) -> None:
        self._seen.pop(key, None)

    def pop_stale(self) -> list[K]:
        stale = [key for key, generation in self._seen.items() if generation < self._current]
        for key in stale:
            del self._seen[key]
        return stale
