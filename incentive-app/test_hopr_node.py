import asyncio
import pprint
from tools import HoprdAPIHelper, _getlogger

log = _getlogger()


async def main():
    host = "http://localhost:13303"
    key = "%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%"

    api = HoprdAPIHelper(host, key)

    address = await api.get_address("hopr")
    print(f"{address=}")
    result = await api.open_channel_safe(
        "16Uiu2HAmAAcAWABt5dhMibBGXHi2UqsspEfqQrno4y2SaCc9PUj6", 1000
    )
    pprint.pprint(result)


if __name__ == "__main__":
    asyncio.run(main())
