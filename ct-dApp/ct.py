import asyncio
import logging
import os
import signal
import sys
import traceback

from hopr_node import HoprNode


# configure and get logger handler
LOGFILE = f"{sys.argv[0]}.log"
FORMAT = "%(levelname)s:%(asctime)s:%(message)s"

logging.basicConfig(filename=LOGFILE, level=logging.INFO, format=FORMAT)
log = logging.getLogger(__name__)


def _getenvvar(name: str) -> str:
    """
    Returns the string contained in environment variable 'name' or None.
    """
    if os.getenv(name) is None:
        raise ValueError(f"Environment variable [{name}] not found")

    return os.getenv(name)


def stop(node: HoprNode, caught_signal):
    """
    Stops the running node
    """
    print(f">>> Caught signal {caught_signal} <<<")
    print(">>> Stopping ...")
    node.stop()


if __name__ == "__main__":
    exit_code = 0

    print(f">>> Program started. Open [ {LOGFILE} ] for logs.")
    print(">>> Press <ctrl+c> to end.")

    # read parameters from environment variables
    try:
        api_host = _getenvvar("HOPR_NODE_1_HTTP_URL")
        api_key = _getenvvar("HOPR_NODE_1_API_KEY")
    except ValueError as e:
        log.error(str(e))
        sys.exit(1)

    node = HoprNode(api_host, api_key)
    loop = asyncio.new_event_loop()

    loop.add_signal_handler(signal.SIGINT, stop, node, signal.SIGINT)
    loop.add_signal_handler(signal.SIGTERM, stop, node, signal.SIGTERM)

    try:
        loop.run_until_complete(node.start())

    except Exception as e:
        log.error("Uncaught exception ocurred", str(e))
        log.error(traceback.format_exc())
        exit_code = 1

    finally:
        node.stop()
        loop.close()
        sys.exit(exit_code)
