from core.rpc.entries import Allocation, ExternalBalance
from core.rpc.providers import MainnetDistributor, wxHOPRBalance
from core.rpc.query_provider import RPCQueryProvider
import pytest

GNOSIS_RPC_URL: str = "https://gnosis-rpc.publicnode.com"
MAINNET_RPC_URL: str = "https://ethereum-rpc.publicnode.com"


@pytest.mark.asyncio
async def test_eoa_balance_provider():
    contract: RPCQueryProvider = wxHOPRBalance(GNOSIS_RPC_URL)

    balance = await contract.balance_of(
        address="0x89c9f05E92Dfb65282Fb4569367b6d33166411C9",
    )
    assert isinstance(balance, ExternalBalance)
    assert balance is not None
    assert balance.amount > 0


@pytest.mark.asyncio
async def test_safe_balance_provider():
    contract: RPCQueryProvider = wxHOPRBalance(GNOSIS_RPC_URL)

    balance = await contract.balance_of(
        address="0x530C90DE63BF1233f84179f312B4dC73727b9C1E",
    )
    assert balance is not None
    assert balance.amount > 0


@pytest.mark.asyncio
async def test_distributor_provider():
    contract: RPCQueryProvider = MainnetDistributor(MAINNET_RPC_URL)

    allocation: Allocation = await contract.allocations(
        address="0x4188a7dca2757ebc7d9a5bd39134a15b9f3c6402",
        schedule="Ecosystem-2022-02",
    )
    assert allocation is not None
    assert allocation.amount > 0
    assert allocation.claimed >= 0
