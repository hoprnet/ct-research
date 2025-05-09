import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from lib.state import State

sys.path.insert(1, "./")

from core.api.hoprd_api import HoprdAPI

load_dotenv()


logger = logging.getLogger("core.api.hoprd_api")
logger.setLevel(logging.INFO)


async def main(deployment: str = "green", environment: str = "staging"):
    host_format = os.getenv("HOST_FORMAT")
    token = os.getenv("TOKEN")

    for idx in range(1, 6):
        host = host_format % (deployment, idx, environment)

        api = HoprdAPI(host, token)

        # get sessions
        sessions = await api.get_sessions()
        for session in sessions:
            await api.close_session(session)

        sessions = await api.get_sessions()
        if len(sessions) != 0:
            print(State.FAILURE, f"[IDX {idx}] Sessions not closed: {sessions}")
            return
        else:
            print(State.SUCCESS, f"[IDX {idx}] Sessions cleanup")


if __name__ == "__main__":
    asyncio.run(main())
