import logging
from typing import Optional

from prometheus_client import Gauge

from ..components.address import Address
from ..components.decorators import connectguard, keepalive, master
from ..components.logs import configure_logging
from .protocols import HasAPI

BALANCE = Gauge("ct_balance", "Node balance", ["address", "token"])
HEALTH = Gauge("ct_node_health", "Node health", ["address"])
TICKET_STATS = Gauge("ct_ticket_stats", "Ticket stats", ["type"])


configure_logging()
logger = logging.getLogger(__name__)


class StateMixin(HasAPI):
    @master(keepalive, connectguard)
    async def retrieve_balances(self):
        """
        Retrieve the balances of the node.
        """
        balances = await self.api.balances()

        if balances is None:
            logger.warning("No results while retrieving balances")
            return None

        if addr := self.address:
            logger.debug(
                "Retrieved balances",
                {key: str(value) for key, value in balances.as_dict.items()},
            )
            for token, balance in vars(balances).items():
                if balance is None:
                    continue
                BALANCE.labels(addr.native, token).set(balance.value)

        return balances

    async def retrieve_address(self) -> Optional[Address]:
        """
        Retrieve the address of the node.
        """
        if address := await self.api.address():
            self.address = Address(address.native)
            logger.debug("Retrieved addresses")
            return self.address
        else:
            logger.warning("No results while retrieving addresses")
            return None

    async def _healthcheck(self):
        """
        Perform a healthcheck on the node.
        """
        self.connected = await self.api.healthyz()

        if addr := await self.retrieve_address():
            if not self.connected:
                logger.warning("Node is not reachable")
            HEALTH.labels(addr.native).set(int(self.connected))
            return addr
        else:
            logger.warning("No address found")
            return None

    @keepalive
    async def healthcheck(self):
        await self._healthcheck()

    @keepalive
    async def ticket_parameters(self):
        """
        Gets the ticket price from the api.
        They are used in the economic model to calculate the number of messages to send to a peer.
        """
        ticket_price = await self.api.ticket_price()

        logger.debug(
            "Fetched ticket price",
            {"value": str(getattr(getattr(ticket_price, "value", None), "value", None))},
        )

        if ticket_price is not None:
            self.ticket_price = ticket_price
            TICKET_STATS.labels("price").set(ticket_price.value.value)
