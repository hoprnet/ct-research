import asyncio
from signal import SIGINT, SIGTERM

import click
import yaml
from prometheus_client import start_http_server

from .components.parameters import Parameters
from .components.utils import Utils
from .core import Core
from .node import Node


@click.command()
@click.option("--configfile", help="The .yaml configuration file to use")
def main(configfile: str = None):
    with open(configfile, "r") as file:
        config = yaml.safe_load(file)

    # import envvars to params, such as self.params.subgraph.deployer_key
    params = Parameters()
    params.parse(config)
    params.from_env("SUBGRAPH", "PG")
    params.overrides("OVERRIDE")

    # create the core and nodes instances
    nodes = Node.fromCredentials(*Utils.nodesCredentials("NODE_ADDRESS", "NODE_KEY"))
    instance = Core(nodes, params)

    # start the prometheus client
    try:
        start_http_server(8080)
    except Exception as e:
        instance.error(f"Could not start the prometheus client on port 8080: {e}")
    else:
        instance.info("Prometheus client started on port 8080")

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
    main()
