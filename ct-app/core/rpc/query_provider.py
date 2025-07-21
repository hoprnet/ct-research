import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import aiohttp

from core.components.logs import configure_logging
from core.rpc.entries.external_balance import ExternalBalance

from .entries.allocation import Allocation

BLOCK_SIZE: int = 64

configure_logging()
logger = logging.getLogger(__name__)


class ProviderError(Exception):
    pass


class RPCQueryProvider:
    method: str = ""

    def __init__(self, url: str):
        self.url = url
        self.pwd = Path(sys.modules[self.__class__.__module__].__file__).parent
        self.query = {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": [{"to": "", "data": ""}, "latest"],
            "id": 1,
        }

    #### PRIVATE METHODS ####
    async def _execute(self, to: str, data: list[str]) -> tuple[dict, dict]:
        self.query["params"][0]["to"] = to
        self.query["params"][0]["data"] = data

        while True:
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(self.url, json=self.query) as response,
                ):
                    return await response.json(), response.status
            except TimeoutError as err:
                logger.error("Timeout error", {"error": str(err)})
                await asyncio.sleep(0.2)  # Retry after a short delay
            except Exception as err:
                logger.error("Unknown error", {"error": str(err)})
                await asyncio.sleep(0.2)  # Retry after a short delay
                
    #### PUBLIC METHODS ####
    def convert_result(self, result: dict, status: int) -> Any:
        return result

    async def get(self, to: str, data: list[str], timeout: int = 30) -> Any:
        try:
            res = await asyncio.wait_for(self._execute(to, data), timeout)
        except asyncio.TimeoutError:
            logger.error(f"Request to {self.url} timed out after {timeout} seconds")
            return self.convert_result({}, 504)  # HTTP 504 Gateway Timeout
        else:
            return self.convert_result(*res)


class ETHCallRPCProvider(RPCQueryProvider):
    method: str = "eth_call"

    def convert_result(self, result: dict, status: int) -> Any:
        if status != 200:
            raise ProviderError(f"Error fetching data: {result.get('error', 'Unknown error')}")

        if "result" not in result:
            raise ProviderError("Invalid response format: 'result' key not found")

        if not isinstance(result["result"], str):
            raise ProviderError("Invalid response format: 'result' should be a hex string")

        return result["result"]


class BalanceProvider(ETHCallRPCProvider):
    token_contract: str = ""
    symbol: str = ""

    async def balance_of(self, address: str) -> ExternalBalance:
        result = await self.get(
            to=self.token_contract,
            data="0x70a08231" + address.lower().replace("0x", "").rjust(BLOCK_SIZE, "0"),
        )
        try:
            balance = str(int(result, 16))
        except ValueError as e:
            logger.error("Failed to parse balance", {"address": address, "error": str(e)})
            raise ProviderError(f"Invalid balance format for address {address}: {result}")

        return ExternalBalance(address, balance)


class DistributorProvider(ETHCallRPCProvider):
    contract: str = ""
    symbol: str = ""

    async def allocations(self, address: str, schedule: str) -> Allocation:
        encoded_schedule: str = schedule.encode().hex()
        data_offset = len(encoded_schedule) // 2

        result = await self.get(
            to=self.contract,
            data="0xc31cd7d7"
            + address.lower().replace("0x", "").rjust(BLOCK_SIZE, "0")
            + hex(BLOCK_SIZE)[2:].rjust(BLOCK_SIZE, "0")
            + hex(data_offset)[2:].rjust(BLOCK_SIZE, "0")
            + encoded_schedule.ljust(BLOCK_SIZE, "0"),
        )

        # split the result into 4 blocks of 64 charaters
        blocks = [result[2 + i * BLOCK_SIZE : 2 + (i + 1) * BLOCK_SIZE] for i in range(4)]
        return Allocation(
            address,
            schedule,
            str(int(blocks[0], 16)),
            str(int(blocks[1], 16)),
        )
