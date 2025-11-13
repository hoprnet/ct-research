import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(1, "./")

from api_lib.headers.authorization import Bearer

from core.api.hoprd_api import HoprdAPI
from scripts.lib.state import State

load_dotenv()


logger = logging.getLogger("core.api.hoprd_api")
logger.setLevel(logging.INFO)


async def main(deployment: str = "green", environment: str = "staging"):
    host_format = os.getenv("HOST_FORMAT")
    token = os.getenv(f"{environment.upper()}_TOKEN")

    if host_format is None or token is None:
        print(State.FAILURE, "HOST_FORMAT or TOKEN not set in .env file")
        return

    apis = [
        HoprdAPI(host_format % (deployment, idx, environment), Bearer(token), "/api/v4")
        for idx in range(1, 6)
    ]

    tasks = set()
    for api in apis:
        for channel in (await api.channels(full_topology=False)).outgoing:
            tasks.add(asyncio.create_task(api.close_channel(channel.id)))

    if not tasks:
        print(State.SUCCESS, "No channels to close")
        return

    results = await asyncio.gather(*tasks)
    print(f"{results=}")


if __name__ == "__main__":
    asyncio.run(main())
