import logging

import click
import yaml
from prometheus_client import start_http_server

from .types.asyncloop import AsyncLoop
from .config_parser import Parameters
from .components.logs import configure_logging
from .node import Node

logger = logging.getLogger(__name__)


@click.command()
@click.option("--configfile", help="The .yaml configuration file to use")
def main(configfile: str):
    configure_logging()

    with open(configfile, "r") as file:
        config = yaml.safe_load(file)

    params = Parameters(config)
    logger.info("Configuration loaded", {"params": str(params)})

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

    # create node instance
    node = Node(params.host.url, params.host.token, params)
    AsyncLoop.run(node.start, node.stop)


if __name__ == "__main__":
    main()
