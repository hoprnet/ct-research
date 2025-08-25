import logging

from ..components.asyncloop import AsyncLoop
from ..components.decorators import keepalive
from ..components.logs import configure_logging
from ..rpc.providers import (
    GnosisDistributor,
    HOPRBalance,
    MainnetDistributor,
    wxHOPRBalance,
    xHOPRBalance,
)
from ..rpc.query_provider import BalanceProvider
from .protocols import HasParams, HasRPCs

configure_logging()
logger = logging.getLogger(__name__)


class RPCMixin(HasParams, HasRPCs):
    @keepalive
    async def allocations(self):
        """
        Gets all allocations for the investors.
        The amount per investor is then added to their stake before dividing it by the number
        of nodes they are running.
        """
        addresses: list[str] = self.params.investors.addresses
        schedule: str = self.params.investors.schedule

        providers = [
            GnosisDistributor(self.params.rpc.gnosis),
            MainnetDistributor(self.params.rpc.mainnet),
        ]

        futures = sum(
            [
                [provider.allocations(addr, schedule) for addr in addresses]
                for provider in providers
            ],
            [],
        )

        self.allocations_data = await AsyncLoop.gather_any(futures)

        logger.debug("Fetched investors allocations", {"counts": len(self.allocations_data)})

    @keepalive
    async def eoa_balances(self):
        """
        Gets the EOA balances on Gnosis and Mainnet for the investors.
        """
        addresses: list[str] = self.params.investors.addresses

        providers: list[BalanceProvider] = [
            HOPRBalance(self.params.rpc.mainnet),
            xHOPRBalance(self.params.rpc.gnosis),
            wxHOPRBalance(self.params.rpc.gnosis),
        ]

        futures = sum(
            [[provider.balance_of(addr) for addr in addresses] for provider in providers], []
        )

        self.eoa_balances_data = await AsyncLoop.gather_any(futures)

        logger.debug("Fetched investors EOA balances", {"count": len(self.eoa_balances_data)})
