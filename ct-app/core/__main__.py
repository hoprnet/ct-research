import logging
import os

import click
import yaml
from prometheus_client import start_http_server

from .components import AsyncLoop
from .components.config_parser import Parameters
from .components.logs import configure_logging
from .node import Node

configure_logging()
logger = logging.getLogger(__name__)


@click.command()
@click.option("--configfile", help="The .yaml configuration file to use")
def main(configfile: str):
    with open(configfile, "r") as file:
        config = yaml.safe_load(file)

    params = Parameters(config)
    logger.debug("Safe parameters loaded", {"params": str(params)})

    params.subgraph.set_attribute_from_env("api_key", "SUBGRAPH_API_KEY")
    params.rpc.set_attribute_from_env("gnosis", "RPC_GNOSIS")
    params.rpc.set_attribute_from_env("mainnet", "RPC_MAINNET")

    # start the prometheus client
    try:
        start_http_server(8080)
    except Exception as err:
        logger.exception("Could not start the prometheus client on port 8080", {"error": err})
    else:
        logger.info("Prometheus client started on port 8080")

    # create the core and nodes instances
    host: str = str(os.environ.get("NODE_ADDRESS", "http://localhost:3001"))
    token: str = str(os.environ.get("HOPRD_API_TOKEN"))

    node = Node(host, token, params)
    AsyncLoop.run(node.start, node.stop)


if __name__ == "__main__":
    main()
