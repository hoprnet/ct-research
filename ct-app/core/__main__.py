import logging

import click
import yaml
from prometheus_client import start_http_server

from core.components.logs import configure_logging

from .components import AsyncLoop, Parameters, Utils
from .core import Core
from .node import Node

configure_logging()
logger = logging.getLogger(__name__)


@click.command()
@click.option("--configfile", help="The .yaml configuration file to use")
def main(configfile: str):
    """
    Runs the main CLI command to initialize and start the core service.
    
    Loads configuration from a YAML file, applies environment and override parameters, initializes node credentials, starts a Prometheus metrics server on port 8080, and launches the core asynchronous lifecycle.
    """
    with open(configfile, "r") as file:
        config = yaml.safe_load(file)

    params = Parameters()
    params.parse(config, entrypoint=True)
    params.from_env("SUBGRAPH")
    params.overrides("OVERRIDE")

    # create the core and nodes instances
    nodes = [Node(*pair) for pair in zip(*Utils.nodesCredentials("NODE_ADDRESS", "NODE_KEY"))]

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
