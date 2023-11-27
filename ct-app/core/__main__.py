import asyncio
import subprocess
from signal import SIGINT, SIGTERM

from prometheus_client import start_http_server

from .components.parameters import Parameters
from .components.utils import Utils
from .core import Core
from .node import Node


def main():
    params = Parameters()(
        "DISTRIBUTION_", "SUBGRAPH_", "GCP_", "ECONOMIC_MODEL_", "CHANNEL_", "RABBITMQ_"
    )

    test_lines = [["header"], ["value"]]
    filename = Utils.generateFilename("", "startup", "csv")
    Utils.stringArrayToGCP(params.gcp.bucket, filename, test_lines)

    instance = Core()

    instance.nodes = Node.fromAddressListAndKey(
        *Utils.nodesAddresses("NODE_ADDRESS_", "NODE_KEY")
    )

    instance.params = params
    for node in instance.nodes:
        node.params = params

    # start the prometheus client
    start_http_server(8080)

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
    result = subprocess.run(
        "sh ./scripts/list_required_parameters.sh ./core/".split(),
        capture_output=True,
        text=True,
    ).stdout

    all_set_flag = True
    for var in result.splitlines():
        exists = Utils.envvarExists(var)
        all_set_flag *= exists

        # print var with a leading check mark if it exists or red X (emoji) if it doesn't
        print(f"{'✅' if exists else '❌'} {var}")

    if all_set_flag:
        main()
    else:
        print("Some required environment variables are missing !")

# TODO Replace prints by logs
