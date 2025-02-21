import logging

import click
import yaml
from prometheus_client import start_http_server

from core.components.logs import configure_logging

from .components import AsyncLoop, Parameters, Utils
from .components.messages import MessageQueue
from .core import Core
from .node import Node

configure_logging()
logger = logging.getLogger(__name__)


@click.command()
@click.option("--configfile", help="The .yaml configuration file to use")
def main(configfile: str):
    with open(configfile, "r") as file:
        config = yaml.safe_load(file)

    params = Parameters()
    params.parse(config, entrypoint=True)
    params.from_env("SUBGRAPH", "PG")
    params.overrides("OVERRIDE")

    # create the core and nodes instances
    nodes = Node.fromCredentials(*Utils.nodesCredentials("NODE_ADDRESS", "NODE_KEY"))

    # start the prometheus client
    try:
        start_http_server(8080)
    except Exception as e:
        logger.exception("Could not start the prometheus client on port 8080", {"error": e})
    else:
        logger.info("Prometheus client started on port 8080")

    core = Core(nodes, params)

    AsyncLoop.run(core.start, core.stop)

    MessageQueue.clear()


if __name__ == "__main__":
    main()
