import asyncio
import logging
import os, sys

from hopr_node import HoprNode


# configure and get logger handler
LOGFILE = '{}.log'.format(sys.argv[0])
logging.basicConfig(filename=LOGFILE,
                    level=logging.INFO,
                    format='%(levelname)s:%(asctime)s:%(message)s')
log = logging.getLogger(__name__)



def _getenvvar(name: str) -> str:
    """
    Returns the string contained in environment variable 'name' or None.
    """
    ret_value = None
    if os.getenv(name) is None:
        log.error("Environment variable [", name, "] not found")
        sys.exit(1)
    else:
        ret_value = os.getenv(name)
    return ret_value


if __name__ == "__main__":
    # read parameters from environment variables
    api_host = _getenvvar('HOPR_NODE_1_HTTP_URL')
    api_key  = _getenvvar('HOPR_NODE_1_API_KEY')

    print(">>> Program started. Open {} for logs.".format(LOGFILE))
    print(">>> Press <ctrl+c> to end.")

    loop = asyncio.new_event_loop()
    node = HoprNode(api_host, api_key)

    try:
        node.connect()

        # start asynchronous tasks
        task0 = loop.create_task(node.gather_peers())
        loop.run_until_complete(task0)

    except KeyboardInterrupt:
        pass

    finally:
        task0.cancel()
        loop.run_until_complete(task0)
        node.disconnect()
        loop.close()
        sys.exit(0)
