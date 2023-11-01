import asyncio
from signal import SIGINT, SIGTERM

from .ctcore import CTCore
from .node import Node
from .parameters import Parameters


def get_nodes(count: int):
    """
    Get nodes.
    """
    parameters = Parameters()
    nodes = set(Node(f"address_{i}", f"key_{i}") for i in range(count))

    for node in nodes:
        node.parameters = parameters
    return nodes


def main():
    instance = CTCore()
    instance.nodes = get_nodes(3)

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, instance.stop)
    loop.add_signal_handler(SIGTERM, instance.stop)

    loop.run_until_complete(instance.start())

    instance.stop()
    loop.close()


if __name__ == "__main__":
    main()
