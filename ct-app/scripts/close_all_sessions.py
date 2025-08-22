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

    for idx in range(1, 6):
        host = host_format % (deployment, idx, environment)

        api = HoprdAPI(host, Bearer(token), "/api/v4")

        # get sessions
        sessions = await api.list_sessions()
        for session in sessions:
            await api.close_session(session)

        sessions = await api.list_sessions()
        if len(sessions) != 0:
            print(State.FAILURE, f"[IDX {idx}] Sessions not closed: {sessions}")
            return
        else:
            print(State.SUCCESS, f"[IDX {idx}] Sessions cleanup")


if __name__ == "__main__":
    asyncio.run(main())
