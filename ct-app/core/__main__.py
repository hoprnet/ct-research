import logging
import os

import click
import yaml
from prometheus_client import start_http_server

from .types.asyncloop import AsyncLoop
from .config_parser import Parameters
from .components.logs import configure_logging
from .node import Node

logger = logging.getLogger(__name__)


def validate_runtime_config(host: str, token: str, params) -> None:
    if not host.strip():
        raise ValueError("HOPRD_API_HOST must not be empty")

    if not token.strip():
        raise ValueError("HOPRD_API_TOKEN must be set")

    blokli_url = getattr(params.blokli, "url", "")
    if not isinstance(blokli_url, str) or not blokli_url.strip():
        raise ValueError("BLOKLI_URL or blokli.url must be set")


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

    # create the core and nodes instances
    host: str = str(os.environ.get("HOPRD_API_HOST", "http://127.0.0.1:3001"))
    token: str = str(os.environ.get("HOPRD_API_TOKEN", ""))
    validate_runtime_config(host, token, params)

    logger.info("Node configuration", {"host": host, "token_set": bool(token)})
    node = Node(host, token, params)
    AsyncLoop.run(node.start, node.stop)


if __name__ == "__main__":
    main()
