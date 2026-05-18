import asyncio
import logging
from typing import Any

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
    @staticmethod
    def _find_config_value(config: Any, keys: set[str]) -> Any:
        if isinstance(config, dict):
            for key, value in config.items():
                if key in keys:
                    return value
                nested = StateMixin._find_config_value(value, keys)
                if nested is not None:
                    return nested
        elif isinstance(config, list):
            for item in config:
                nested = StateMixin._find_config_value(item, keys)
                if nested is not None:
                    return nested
        return None

    async def load_static_ticket_parameters_from_node_configuration(self) -> tuple[bool, bool]:
        configuration = await self.api.configuration()
        if not isinstance(configuration, dict):
            logger.warning("Could not load node configuration for static ticket parameters")
            return False, False

        static_ticket_price = False
        static_winning_probability = False

        ticket_price_value = self._find_config_value(configuration, {"ticket_price", "ticketPrice"})
        if ticket_price_value not in (None, ""):
            try:
                ticket_price = TicketPrice({"price": str(ticket_price_value)})
                self.ticket_price = ticket_price
                TICKET_STATS.labels("price").set(float(ticket_price.value.value))
                static_ticket_price = True
            except Exception as error:
                logger.warning(
                    "Invalid static ticket price in node configuration",
                    {"value": ticket_price_value, "error": str(error)},
                )

        winning_probability_value = self._find_config_value(
            configuration,
            {"min_ticket_winning_probability", "minTicketWinningProbability"},
        )
        if winning_probability_value not in (None, ""):
            try:
                probability = float(winning_probability_value)
                self.min_ticket_winning_probability = probability
                TICKET_STATS.labels("min_ticket_winning_probability").set(probability)
                static_winning_probability = True
            except (TypeError, ValueError) as error:
                logger.warning(
                    "Invalid static minimum ticket winning probability in node configuration",
                    {"value": winning_probability_value, "error": str(error)},
                )

        if static_ticket_price or static_winning_probability:
            self.network_update_coordinator.request("ticket_parameters_configuration")
            logger.info(
                "Loaded static ticket parameters from node configuration",
                {
                    "static_ticket_price": static_ticket_price,
                    "static_winning_probability": static_winning_probability,
                },
            )

        return static_ticket_price, static_winning_probability

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
            if self.ticket_price is None:
                ticket_price = TicketPrice({"price": params.ticket_price.as_str})
                self.ticket_price = ticket_price
                TICKET_STATS.labels("price").set(float(ticket_price.value.value))

            if self.min_ticket_winning_probability is None:
                self.min_ticket_winning_probability = params.min_ticket_winning_probability
                TICKET_STATS.labels("min_ticket_winning_probability").set(
                    params.min_ticket_winning_probability
                )

            logger.info(
                "Updated ticket parameters from Blokli subscription",
                {
                    "ticket_price": self.ticket_price.value.as_str if self.ticket_price else None,
                    "min_ticket_winning_probability": self.min_ticket_winning_probability,
                },
            )
            self.network_update_coordinator.request("ticket_parameters_subscription")
