import asyncio
from ..exit_codes import ExitCode
from ..utils import _getenvvar
from .economic_handler import EconomicHandler

async def main():
    """main"""
    try:
        API_host = _getenvvar("HOPR_NODE_1_HTTP_URL")
        API_key = _getenvvar("HOPR_NODE_1_API_KEY")
    except ValueError:
        exit(ExitCode.ERROR_BAD_ARGUMENTS)

    print(API_host)
    print(API_key)

    economic_handler = EconomicHandler(API_host, API_key)
    result = await economic_handler.channel_topology()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())

