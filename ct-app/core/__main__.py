import asyncio
import logging
from signal import SIGINT, SIGTERM

from .components.utils import Utils
from .ctcore import CTCore
from .model import Parameters
from .node import Node

logger = logging.getLogger()


def get_nodes():
    parameters = Parameters()
    addresses = Utils.envvar_with_prefix("NODE_ADDRESS_")
    key = Utils.envvar("NODE_KEY")

    nodes = {Node(address, key) for address in addresses}

    for node in nodes:
        node.parameters = parameters

    return nodes


def main():
    instance = CTCore()
    instance.nodes = get_nodes()

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, instance.stop)
    loop.add_signal_handler(SIGTERM, instance.stop)

    loop.run_until_complete(instance.start())

    instance.stop()
    loop.close()


if __name__ == "__main__":
    main()
