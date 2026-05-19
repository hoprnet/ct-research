import logging
from decimal import Decimal
from typing import Any

from prometheus_client import Gauge

from ..types.balance import Balance
from ..config_parser.economic_model import LegacyParams, SigmoidParams
from .runtime_state import NodeRuntimeState

ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")
MESSAGE_COUNT = Gauge(
    "ct_message_count", "messages one should receive / year", ["address", "model"]
)

logger = logging.getLogger(__name__)


class EconomicSystemMixin(NodeRuntimeState):
    def _economic_inputs_ready(self) -> bool:
        node_to_safe = getattr(self.network_state, "node_to_safe", {})
        safe_balances = getattr(self.network_state, "safe_balances", {})
        mapped_safes = {
            node_to_safe.get(peer.address.native)
            for peer in self.peers.values()
            if node_to_safe.get(peer.address.native) is not None
        }

        if not mapped_safes:
            logger.warning("Skipping economic model: node-safe links are not available yet")
            return False

        if not any(safe in safe_balances for safe in mapped_safes):
            logger.warning("Skipping economic model: safe balances are not available yet")
            return False

        return True

    async def _apply_economic_model_once(self):
        if not self.peers:
            logger.warning("Skipping economic model: reachable peers are not available yet")
            return

        if self.ticket_price is None:
            logger.warning("Skipping economic model: ticket price is not available yet")
            return

        if not self._economic_inputs_ready():
            return

        eligible_peers = []
        for p in self.peers.values():
            is_eligible = p.is_eligible(
                self.params.economic_model.legacy.coefficients.lowerbound,
                self.params.sessions.blue_destinations + self.params.sessions.green_destinations,
                self.params.peer.excluded_peers,
            )
            if not is_eligible:
                p.yearly_message_count = None
                continue
            eligible_peers.append(p)

        economic_security = (
            sum(
                [p.effective_stake for p in eligible_peers],
                Balance.zero("wxHOPR"),
            )
            / self.params.economic_model.sigmoid.total_token_supply
        )
        network_capacity = Decimal(
            len(eligible_peers) / self.params.economic_model.sigmoid.network_capacity
        )

        message_count: dict[type, float] = {model: 0 for model in self.params.economic_model.models}
        model_input: dict[type, Any] = {model: None for model in self.params.economic_model.models}

        model_input[SigmoidParams] = [economic_security, network_capacity]

        for peer in eligible_peers:
            model_input[LegacyParams] = peer.redeemed_amount or Balance.zero("wxHOPR")

            for model, name in self.params.economic_model.models.items():
                message_count[model] = getattr(
                    self.params.economic_model, name
                ).yearly_message_count(
                    peer.effective_stake,
                    self.ticket_price,
                    model_input[model],
                ) / (
                    len(self.session_destinations) + 1
                )

                MESSAGE_COUNT.labels(peer.address.native, name).set(message_count[model])

            peer.yearly_message_count = sum(message_count.values())

        eligible_count = sum([p.yearly_message_count is not None for p in self.peers.values()])
        expected_rate = sum(
            [1 / p.message_delay for p in self.peers.values() if p.message_delay is not None]
        )
        logger.info(
            "Generated the eligible nodes set",
            {"count": eligible_count, "expected_rate": expected_rate},
        )
        ELIGIBLE_PEERS.set(eligible_count)

    def trigger_economic_model_refresh(self) -> None:
        self.economic_model_refresh_coordinator.request()
