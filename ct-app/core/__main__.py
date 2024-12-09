import click
import yaml
from prometheus_client import start_http_server

from .components import AsyncLoop, Base, Parameters, Utils
from .components.messages import MessageQueue
from .core import Core
from .model.database import DatabaseConnection
from .node import Node


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
        Base.logger.error(f"Could not start the prometheus client on port 8080: {e}")
    else:
        Base.logger.info("Prometheus client started on port 8080")

    DatabaseConnection.open(params.pg)

    AsyncLoop.run(Core(nodes, params).start)

    MessageQueue.clear()

    DatabaseConnection.close()


if __name__ == "__main__":
    main()
