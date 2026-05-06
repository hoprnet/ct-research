import logging
from decimal import Decimal
from typing import Any

from prometheus_client import Gauge

from ..types.balance import Balance
from ..config_parser.economic_model import LegacyParams, SigmoidParams
from ..components.decorators import keepalive
from .runtime_state import NodeRuntimeState

ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")
MESSAGE_COUNT = Gauge(
    "ct_message_count", "messages one should receive / year", ["address", "model"]
)

logger = logging.getLogger(__name__)


class EconomicSystemMixin(NodeRuntimeState):
    @keepalive
    async def apply_economic_model(self):
        """
        Applies the economic model to the eligible peers (after multiple filtering layers).
        """

        if not self.peers:
            logger.warning("Not enough data to apply economic model")
            return

        for p in self.peers.values():
            if not p.is_eligible(
                self.params.economic_model.legacy.coefficients.lowerbound,
                self.params.sessions.blue_destinations + self.params.sessions.green_destinations,
                self.params.peer.excluded_peers,
            ):
                p.yearly_message_count = None

        economic_security = (
            sum(
                [
                    p.effective_stake
                    for p in self.peers.values()
                    if p.yearly_message_count is not None
                ],
                Balance.zero("wxHOPR"),
            )
            / self.params.economic_model.sigmoid.total_token_supply
        )
        network_capacity = Decimal(
            len([p for p in self.peers.values() if p.yearly_message_count is not None])
            / self.params.economic_model.sigmoid.network_capacity
        )

        message_count: dict[type, float] = {model: 0 for model in self.params.economic_model.models}
        model_input: dict[type, Any] = {model: None for model in self.params.economic_model.models}

        model_input[SigmoidParams] = [economic_security, network_capacity]

        for peer in self.peers.values():
            if peer.yearly_message_count is None:
                continue

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
