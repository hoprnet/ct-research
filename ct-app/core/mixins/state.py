import asyncio
import logging

from prometheus_client import Gauge

from ..types.address import Address
from ..components.decorators import connectguard, keepalive, master
from ..api.response_objects import TicketPrice
from .runtime_state import NodeRuntimeState

BALANCE = Gauge("ct_balance", "Node balance", ["token"])
HEALTH = Gauge("ct_node_health", "Node health")
TICKET_STATS = Gauge("ct_ticket_stats", "Ticket stats", ["type"])


logger = logging.getLogger(__name__)


class StateMixin(NodeRuntimeState):
    def _resolve_session_destinations(self, address_native: str) -> list[str]:
        if address_native in self.params.sessions.green_destinations:
            return list(self.params.sessions.green_destinations)

        if address_native in self.params.sessions.blue_destinations:
            return list(self.params.sessions.blue_destinations)

        logger.warning("Node address not found in any deployment destinations. Skipping sending")
        return []

    @master(keepalive, connectguard)
    async def retrieve_balances(self):
        """
        Retrieve the balances of the node.
        """
        balances = await self.api.balances()

        if balances is None:
            logger.warning("No results while retrieving balances")
            return None

        logger.info(
            "Retrieved balances",
            {key: str(value) for key, value in balances.as_dict.items()},
        )
        for token, balance in vars(balances).items():
            if balance is None:
                continue
            BALANCE.labels(token).set(balance.value)

        return balances

    async def retrieve_address(self, retry_delay: float = 10.0):
        """
        Retrieve the address of the node.
        """

        address = None
        while not address:
            address = await self.api.address()
            if not address:
                logger.warning(
                    f"No results while retrieving addresses, retrying in {retry_delay}s..."
                )
                await asyncio.sleep(retry_delay)

        self.address = Address(address.native)
        self.connected = True
        destinations = self._resolve_session_destinations(self.address.native)
        self.session_destinations = [item for item in destinations if item != self.address.native]
        logger.info(
            "Node address resolved and destinations configured",
            {
                "address": self.address.native,
                "destinations_count": len(self.session_destinations),
            },
        )

    @keepalive
    async def healthcheck(self):
        """
        Perform a healthcheck on the node.
        """
        self.connected = await self.api.healthyz()

        if not self.connected:
            logger.warning("Node is not reachable")
        HEALTH.set(int(self.connected))

    async def ticket_parameters(self):
        """
        Subscribes to Blokli ticket parameter updates.
        They are used in the economic model to calculate the number of messages to send to a peer.
        """
        async for params in self.blokli_repository.stream_ticket_parameters():
            ticket_price = TicketPrice({"price": params.ticket_price.as_str})
            logger.info(
                "Updated ticket parameters from Blokli subscription",
                {
                    "ticket_price": ticket_price.value.as_str,
                    "min_ticket_winning_probability": params.min_ticket_winning_probability,
                },
            )

            self.ticket_price = ticket_price
            self.min_ticket_winning_probability = params.min_ticket_winning_probability
            TICKET_STATS.labels("price").set(float(ticket_price.value.value))
            TICKET_STATS.labels("min_ticket_winning_probability").set(
                params.min_ticket_winning_probability
            )
            self.network_update_coordinator.request("ticket_parameters_subscription")
