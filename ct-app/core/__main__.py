import logging
import os

import click
import yaml
from prometheus_client import start_http_server

from core.components.config_parser import Parameters
from core.components.logs import configure_logging

from .components import AsyncLoop, Utils
from .core import Core
from .node import Node

configure_logging()
logger = logging.getLogger(__name__)


@click.command()
@click.option("--configfile", help="The .yaml configuration file to use")
def main(configfile: str):
    with open(configfile, "r") as file:
        config = yaml.safe_load(file)

    params = Parameters(config)
    logger.debug("Safe parameters loaded", {"params": params.as_dict()})

    params.subgraph.api_key = os.getenv("SUBGRAPH_API_KEY", "")
    logger.debug("API key loaded")

    # create the core and nodes instances
    nodes = [
        Node(host, key) for host, key in zip(*Utils.nodesCredentials("NODE_ADDRESS", "NODE_KEY"))
    ]

    # start the prometheus client
    try:
        start_http_server(8080)
    except Exception as err:
        logger.exception("Could not start the prometheus client on port 8080", {"error": err})
    else:
        logger.info("Prometheus client started on port 8080")

    core = Core(nodes, params)

    AsyncLoop.run(core.start, core.stop)


if __name__ == "__main__":
    main()
