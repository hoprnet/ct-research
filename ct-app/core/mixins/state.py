import asyncio
import logging

from prometheus_client import Gauge

from ..components.address import Address
from ..components.decorators import connectguard, keepalive, master
from ..components.logs import configure_logging
from .protocols import HasAPI, HasParams, HasSession

BALANCE = Gauge("ct_balance", "Node balance", ["token"])
HEALTH = Gauge("ct_node_health", "Node health")
TICKET_STATS = Gauge("ct_ticket_stats", "Ticket stats", ["type"])


configure_logging()
logger = logging.getLogger(__name__)


class StateMixin(HasAPI, HasParams, HasSession):
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

        if self.address.native in self.params.sessions.green_destinations:
            self.session_destinations = self.params.sessions.green_destinations
        elif self.address.native in self.params.sessions.blue_destinations:
            self.session_destinations = self.params.sessions.blue_destinations
        else:
            logger.warning(
                "Node address not found in any deployment destinations. Skipping sending"
            )

        if self.session_destinations:
            self.session_destinations = [
                item for item in self.session_destinations if item != self.address.native
            ]

    @keepalive
    async def healthcheck(self):
        """
        Perform a healthcheck on the node.
        """
        self.connected = await self.api.healthyz()

        if not self.connected:
            logger.warning("Node is not reachable")
        HEALTH.set(int(self.connected))

    @keepalive
    async def ticket_parameters(self):
        """
        Gets the ticket price from the api.
        They are used in the economic model to calculate the number of messages to send to a peer.
        """
        ticket_price = await self.api.ticket_price()

        if ticket_price is not None:
            logger.info(
                "Fetched ticket price",
                {"value": ticket_price.value.as_str},
            )

            self.ticket_price = ticket_price
            TICKET_STATS.labels("price").set(ticket_price.value.value)
        else:
            logger.warning("No results while retrieving ticket price")
