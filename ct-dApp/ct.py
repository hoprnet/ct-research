import asyncio
import logging
import os
import signal
import sys
import traceback

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


def stop(node, caught_signal):
    """
    Stops the running node
    """
    print(">>> Caught signal {} <<<".format(caught_signal))
    print(">>> Stopping ...")
    node.stop()
    

if __name__ == "__main__":
    exit_code = 0

    # read parameters from environment variables
    api_host = _getenvvar('HOPR_NODE_1_HTTP_URL')
    api_key  = _getenvvar('HOPR_NODE_1_API_KEY')

    print(">>> Program started. Open [ {} ] for logs.".format(LOGFILE))
    print(">>> Press <ctrl+c> to end.")

    node = HoprNode(api_host, api_key)
    loop = asyncio.new_event_loop()

    try:
        loop.add_signal_handler(signal.SIGINT, lambda: stop(node, signal.SIGINT))
        loop.add_signal_handler(signal.SIGTERM, lambda: stop(node, signal.SIGTERM))

        loop.run_until_complete(node.start())
    
    except Exception as e:
        log.error("Uncaught exception ocurred", str(e))
        log.error(traceback.format_exc())
        exit_code = 1

    finally:
        node.stop()
        loop.close()
        sys.exit(exit_code)
