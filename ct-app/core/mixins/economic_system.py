import logging
from decimal import Decimal

from prometheus_client import Gauge

from ..components.balance import Balance
from ..components.config_parser.economic_model import LegacyParams, SigmoidParams
from ..components.decorators import keepalive
from ..components.logs import configure_logging
from ..components.utils import Utils
from .protocols import HasNFT, HasParams, HasPeers, HasRPCs, HasSession, HasSubgraphs

ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")
MESSAGE_COUNT = Gauge(
    "ct_message_count", "messages one should receive / year", ["address", "model"]
)

configure_logging()
logger = logging.getLogger(__name__)


class EconomicSystemMixin(HasNFT, HasParams, HasPeers, HasRPCs, HasSession, HasSubgraphs):
    @keepalive
    async def apply_economic_model(self):
        """
        Applies the economic model to the eligible peers (after multiple filtering layers).
        """

        if not all([len(self.topology_data), len(self.registered_nodes_data), len(self.peers)]):
            logger.warning("Not enough data to apply economic model")
            return

        Utils.associateEntitiesToNodes(self.allocations_data, self.registered_nodes_data)
        Utils.associateEntitiesToNodes(self.eoa_balances_data, self.registered_nodes_data)

        await Utils.mergeDataSources(
            self.topology_data,
            self.peers,
            self.registered_nodes_data,
            self.allocations_data,
            self.eoa_balances_data,
        )

        Utils.allowManyNodePerSafe(self.peers)

        for p in self.peers:
            if not p.is_eligible(
                self.params.economic_model.min_safe_allowance,
                self.params.economic_model.legacy.coefficients.lowerbound,
                self.nft_holders_data,
                self.params.economic_model.nft_threshold,
                self.params.sessions.blue_destinations + self.params.sessions.green_destinations,
            ):
                p.yearly_message_count = None

        economic_security = (
            sum(
                [p.split_stake for p in self.peers if p.yearly_message_count is not None],
                Balance.zero("wxHOPR"),
            )
            / self.params.economic_model.sigmoid.total_token_supply
        )
        network_capacity = Decimal(
            len([p for p in self.peers if p.yearly_message_count is not None])
            / self.params.economic_model.sigmoid.network_capacity
        )

        message_count = {model: 0 for model in self.params.economic_model.models}
        model_input = {model: None for model in self.params.economic_model.models}

        model_input[SigmoidParams] = [economic_security, network_capacity]

        for peer in self.peers:
            if peer.yearly_message_count is None:
                continue

            model_input[LegacyParams] = self.peers_rewards_data.get(
                peer.address.native, Balance.zero("wxHOPR")
            )

            for model, name in self.params.economic_model.models.items():
                message_count[model] = getattr(
                    self.params.economic_model, name
                ).yearly_message_count(
                    peer.split_stake,
                    self.ticket_price,
                    model_input[model],
                ) / (
                    len(self.session_destinations) + 1
                )

                MESSAGE_COUNT.labels(peer.address.native, name).set(message_count[model])

            peer.yearly_message_count = sum(message_count.values())

        eligible_count = sum([p.yearly_message_count is not None for p in self.peers])
        expected_rate = sum(
            [1 / p.message_delay for p in self.peers if p.message_delay is not None]
        )
        logger.info(
            "Generated the eligible nodes set",
            {"count": eligible_count, "expected_rate": expected_rate},
        )
        ELIGIBLE_PEERS.set(eligible_count)
