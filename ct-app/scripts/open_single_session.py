import asyncio
import logging
import os
import random
import sys

from dotenv import load_dotenv

sys.path.insert(1, "./")
from api_lib.headers.authorization import Bearer

from core.api.hoprd_api import HoprdAPI
from core.components.logs import configure_logging
from core.components.node_helper import NodeHelper
from core.components.pattern_matcher import PatternMatcher
from scripts.lib.state import State

load_dotenv()

configure_logging()
logger = logging.getLogger("api-lib")
logger.setLevel(logging.INFO)


def p2p_endpoint(api_endpoint: str, env: str):
    target_url = "ctdapp-{}-node-{}-p2p.ctdapp.{}.hoprnet.link"
    patterns: list[PatternMatcher] = [
        PatternMatcher(r"ctdapp-([a-zA-Z]+)-node-(\d+)\.ctdapp\.([a-zA-Z]+)"),
        PatternMatcher(r"ctdapp-([a-zA-Z]+)-node-(\d+)-p2p-tcp", env),
    ]

    for pattern in patterns:
        if groups := pattern.search(api_endpoint):
            return target_url.format(*groups)

    logger.error("No match found for p2p endpoint, using url")

    return api_endpoint


async def main(deployment: str = "green", environment: str = "staging"):
    host_format = os.getenv("HOST_FORMAT")
    token = os.getenv(f"{environment.upper()}_TOKEN")

    if host_format is None or token is None:
        logger.info(State.FAILURE, "HOST_FORMAT or TOKEN not set in .env file")
        return

    apis: list[HoprdAPI] = [
        HoprdAPI(host_format % (deployment, idx, environment), Bearer(token), "/api/v4")
        for idx in range(2, 6)
    ]

    rand_apis: list[HoprdAPI] = random.sample(apis, k=2)
    dst_address = await rand_apis[1].address()
    relayer: str = "0x56425002D7912e35d8D7F35575B1ec4c9f547D73"

    logger.info(f"{rand_apis[0].host} <> {relayer} <> {rand_apis[1].host}")

    for session in await rand_apis[0].list_sessions():
        await NodeHelper.close_session(rand_apis[0], session)

    await NodeHelper.open_session(
        rand_apis[0],
        dst_address.native,
        relayer,
        p2p_endpoint(rand_apis[0].host, environment),
    )


if __name__ == "__main__":
    asyncio.run(main())
