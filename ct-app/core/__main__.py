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
    logger.info("Safe parameters loaded", {"params": str(params)})

    params.subgraph.set_attribute_from_env("api_key", "SUBGRAPH_API_KEY")

    # start the prometheus client
    prometheus_server_port = 8081
    try:
        start_http_server(prometheus_server_port)
    except OSError as err:
        logger.error(
            "Could not start the prometheus client",
            {"port": prometheus_server_port, "error": f"[Errno {err.args[0]}]: {err.args[1]}"},
        )
    except Exception:
        logger.exception("Unexpected error starting the prometheus client")
    else:
        logger.info("Prometheus client started", {"port": prometheus_server_port})

    # create the core and nodes instances
    host: str = str(os.environ.get("HOPRD_API_HOST", "http://127.0.0.1:3001"))
    token: str = str(os.environ.get("HOPRD_API_TOKEN"))

    logger.info("Node configuration", {"host": host, "token_set": bool(token)})
    node = Node(host, token, params)
    AsyncLoop.run(node.start, node.stop)


if __name__ == "__main__":
    main()
