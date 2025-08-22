import logging

from prometheus_client import Gauge

from ..components.decorators import keepalive
from ..components.logs import configure_logging
from ..subgraph import URL, Type, entries
from .protocols import HasParams, HasSubgraphs

STAKE = Gauge("ct_peer_stake", "Stake", ["safe", "type"])
SUBGRAPH_SIZE = Gauge("ct_subgraph_size", "Size of the subgraph")
REDEEMED_REWARDS = Gauge("ct_redeemed_rewards", "Redeemed rewards", ["address"])

configure_logging()
logger = logging.getLogger(__name__)


class SubgraphMixin(HasParams, HasSubgraphs):
    def get_graphql_providers(self):
        user_id = self.params.subgraph.user_id
        api_key = self.params.subgraph.api_key

        self.graphql_providers = {
            s: s.provider(URL(user_id, api_key, getattr(self.params.subgraph, s.value)))
            for s in Type
        }

    @keepalive
    async def rotate_subgraphs(self):
        """
        Checks the subgraph URLs and sets the subgraph mode in use (default, backup or none).
        """
        logger.info("Rotating subgraphs")
        for provider in self.graphql_providers.values():
            await provider.test(self.params.subgraph.type)

    @keepalive
    async def peers_rewards(self):
        results = dict()
        for acc in await self.graphql_providers[Type.REWARDS].get():
            account = entries.Account(acc["id"], acc["redeemedValue"])
            results[account.address] = account.redeemed_value
            REDEEMED_REWARDS.labels(account.address).set(
                account.redeemed_value.value  # ty: ignore[invalid-argument-type]
            )

        self.peers_rewards_data = results
        logger.debug("Fetched peers rewards amounts", {"count": len(results)})

    @keepalive
    async def registered_nodes(self):
        """
        Gets all registered nodes in the Network Registry.
        """

        results = list[entries.Node]()
        for safe in await self.graphql_providers[Type.SAFES].get():
            results.extend(
                [
                    entries.Node.fromSubgraphResult(node)
                    for node in safe["registeredNodesInSafeRegistry"]
                ]
            )

        for node in results:
            STAKE.labels(node.safe.address, "balance").set(float(node.safe.balance.value))
            STAKE.labels(node.safe.address, "allowance").set(float(node.safe.allowance.value))
            STAKE.labels(node.safe.address, "additional_balance").set(
                node.safe.additional_balance.value
            )

        self.registered_nodes_data = results
        logger.debug("Fetched registered nodes in the safe registry", {"count": len(results)})
        SUBGRAPH_SIZE.set(len(results))
