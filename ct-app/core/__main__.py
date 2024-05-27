import asyncio
from signal import SIGINT, SIGTERM

from prometheus_client import start_http_server

from .components.parameters import Parameters
from .components.utils import Utils
from .core import Core
from .node import Node


def main():
    params = Parameters()(
        "DISTRIBUTION_",
        "SUBGRAPH_",
        "GCP_",
        "ECONOMIC_MODEL_",
        "CHANNEL_",
        "RABBITMQ_",
        "PEER_",
    )

    Utils.stringArrayToGCP(
        params.gcp.bucket,
        Utils.generateFilename("", "startup", "csv"),
        [["header"], ["value"]],
    )

    # create the core and nodes instances
    instance = Core()
    nodes = Node.fromAddressAndKeyLists(
        *Utils.nodesAddresses("NODE_ADDRESS_", "NODE_KEY_")
    )

    instance.post_init(nodes, params)

    # start the prometheus client
    try:
        start_http_server(8080)
    except OSError:
        instance.error("Address already in use, prometheus client not started")

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, instance.stop)
    loop.add_signal_handler(SIGTERM, instance.stop)

    try:
        loop.run_until_complete(instance.start())
    except asyncio.CancelledError:
        instance.error("Stopping the instance...")
    finally:
        instance.stop()
        loop.close()


if __name__ == "__main__":
    if Utils.checkRequiredEnvVar("core"):
        main()
