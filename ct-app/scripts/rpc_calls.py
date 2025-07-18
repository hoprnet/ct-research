import asyncio
import sys

sys.path.insert(1, "./")
from core.components.balance import Balance
from core.rpc.entries.allocation import Allocation
from core.rpc.providers import GNOBalance, MainnetDistributor, xHOPRBalance
from core.rpc.query_provider import RPCQueryProvider

GNOSIS_RPC_URL: str = "https://gnosis-rpc.publicnode.com"
MAINNET_RPC_URL: str = "https://ethereum-rpc.publicnode.com"


async def main():
    # region Example usage of BalanceProvider
    gno_contract: RPCQueryProvider = GNOBalance(GNOSIS_RPC_URL)

    eoa_balance: Balance = await gno_contract.balance_of(
        address="0x864956660E27E145659a681B09D37c728f3322C2",
    )
    print(eoa_balance)

    safe_balance: Balance = await gno_contract.balance_of(
        address="0xD9a00176Cf49dFB9cA3Ef61805a2850F45Cb1D05",
    )
    print(safe_balance)

    xhopr_balance: Balance = await xHOPRBalance(GNOSIS_RPC_URL).balance_of(
        address="0xCC8767dCb5249ed6D72E7A1Df44Dff89ebCE4882"
    )
    print(xhopr_balance)
    # endregion

    # region Example usage of GnosisAllocationProvider
    distributor_contract: RPCQueryProvider = MainnetDistributor(MAINNET_RPC_URL)

    allocation: Allocation = await distributor_contract.allocations(
        address="0xebad8a12451bd17f7708a325a150f06cb0ec6e7c",
        schedule="investor-node-remainder-2024-01",
    )
    print(allocation)

    allocation: Allocation = await distributor_contract.allocations(
        address="0x6067e32439c70f9549ccb31fa858598b54c48899",
        schedule="token-buyer-2024-01",
    )
    print(allocation)
    # endregion


if __name__ == "__main__":
    asyncio.run(main())
