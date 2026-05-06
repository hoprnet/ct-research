from __future__ import annotations

import logging
import random

from ...api.response_objects import Session
from ...types.message_format import MessageFormat
from ..runtime_state import NodeRuntimeState

logger = logging.getLogger(__name__)

DEFAULT_SESSION_GRACE_PERIOD_SECONDS = 60
DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_IN_FLIGHT_WAIT_SECONDS = 3.0


class SessionCommonMixin(NodeRuntimeState):
    def _session_has_in_flight_tasks(self, session: "Session") -> bool:
        return bool(self._in_flight_tasks_by_session_port.get(session.port))

    @staticmethod
    def _normalize_destination(destination: str | None) -> str:
        return destination.lower() if destination else ""

    @property
    def peer_addresses(self) -> set[str]:
        if self._cached_peer_addresses is None:
            self._cached_peer_addresses = {peer.address.native for peer in self.peers.values()}
        return self._cached_peer_addresses

    @property
    def reachable_destinations(self) -> set[str]:
        if self._cached_reachable_destinations is None:
            self._cached_reachable_destinations = (
                set(self.session_destinations) & self.peer_addresses
            )
        return self._cached_reachable_destinations

    def _select_session_destination(
        self,
        message: MessageFormat,
        channels: list[str],
    ) -> str | None:
        if not channels:
            logger.debug("No outgoing channels available", {"relayer": message.relayer})
            return None

        if message.relayer not in channels:
            logger.debug(
                "Relayer not found in outgoing channels",
                {"relayer": message.relayer, "channel_count": len(channels)},
            )
            return None

        if not self.session_destinations:
            logger.debug(
                "No session destinations configured for this node", {"relayer": message.relayer}
            )
            return None

        reachable_dest_set = self.reachable_destinations
        candidates = [item for item in reachable_dest_set if item != message.relayer]

        if not candidates:
            reachable_destinations = list(reachable_dest_set)
            logger.debug(
                "No valid session destination found",
                {
                    "relayer": message.relayer,
                    "total_destinations": len(self.session_destinations),
                    "reachable_destinations": len(reachable_destinations),
                    "reachable_peers": len(self.peer_addresses),
                    "reason": (
                        "no_reachable_destinations"
                        if not reachable_destinations
                        else "all_reachable_are_relayer"
                    ),
                },
            )
            return None

        return random.choice(candidates)

    def _session_matches_destination(self, session: "Session", destination: str) -> bool:
        return self._normalize_destination(session.target) == self._normalize_destination(
            destination
        )
