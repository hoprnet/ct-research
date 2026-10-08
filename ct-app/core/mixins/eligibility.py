import logging
from typing import Any

from prometheus_client import Gauge

from ..messages.message_metrics import BURST_PACKETS_ECHOED, BURST_PACKETS_SENT
from ..services.eligibility import is_eligible
from .runtime_state import NodeRuntimeState

ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")

logger = logging.getLogger(__name__)


class EligibilityMixin(NodeRuntimeState):
    @staticmethod
    def _configured_ct_nodes(params: Any) -> set[str]:
        sessions = getattr(params, "sessions", None)
        blue_destinations = list(getattr(sessions, "blue_destinations", []) or [])
        green_destinations = list(getattr(sessions, "green_destinations", []) or [])
        return {address.lower() for address in blue_destinations + green_destinations}

    def _compute_eligible_relayers(self) -> set[str]:
        ct_nodes = self._configured_ct_nodes(self.params)
        if self.address is not None:
            ct_nodes.add(self.address.native)
        exclusion_list = {address.lower() for address in self.params.peer.excluded_peers or []}
        min_outgoing_channels = self.params.incentive.min_outgoing_channels

        return {
            address
            for address, peer in self.peers.items()
            if is_eligible(
                address,
                peer.reachable,
                peer.qualifying_channels,
                min_outgoing_channels,
                ct_nodes,
                exclusion_list,
            )
        }

    async def _refresh_eligibility_once(self) -> None:
        eligible = self._compute_eligible_relayers()
        joined = eligible - self.eligible_relayers
        left = self.eligible_relayers - eligible
        self.eligible_relayers = eligible
        ELIGIBLE_PEERS.set(len(eligible))

        # Export the per-relayer burst counters at 0 before the relayer's first burst. A relayer
        # gets one burst per round (~50 min), and `rate()` ignores a series' first sample, so a
        # series created by that burst would hide it.
        for relayer in joined:
            BURST_PACKETS_SENT.labels(relayer)
            BURST_PACKETS_ECHOED.labels(relayer)

        if joined or left:
            logger.info(
                "Updated the eligible relayers set",
                {"count": len(eligible), "joined": len(joined), "left": len(left)},
            )

    def trigger_eligibility_refresh(self) -> None:
        self.eligibility_refresh_coordinator.request()
