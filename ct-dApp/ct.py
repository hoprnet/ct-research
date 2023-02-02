import asyncio
import logging
import os
import sys

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


async def producer(node, queue):
    peers_gathered = 0
    max_peers = 10
    while peers_gathered < max_peers:
        await node.gather_peers()
        for p in node.peers:
            await queue.put(p)
            peers_gathered += 1
            
async def consumer(node, queue):
    while True:
        p = await queue.get()
        if p not in node.latency.keys():
            await node.ping_peer(p)
            log.info("Ping sent to peer: {}".format(p))
        queue.task_done()


if __name__ == "__main__":
    # read parameters from environment variables
    api_host = _getenvvar('HOPR_NODE_1_HTTP_URL')
    api_key  = _getenvvar('HOPR_NODE_1_API_KEY')

    print(">>> Program started. Open {} for logs.".format(LOGFILE))
    print(">>> Press <ctrl+c> to end.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    node = HoprNode(api_host, api_key)

    try:
        loop.run_until_complete(node.connect())

        queue = asyncio.Queue()
        tasks = [loop.create_task(producer(node, queue)),
                 loop.create_task(consumer(node, queue))]
        
        loop.run_forever()
        loop.run_until_complete(asyncio.gather(*tasks))
    
    except KeyboardInterrupt:
        pass

    finally:
        for t in tasks:
            t.cancel()
        loop.run_until_complete(asyncio.gather(*tasks))
        node.disconnect()
        loop.close()
        sys.exit(0)
