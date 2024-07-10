import click
import yaml
from prometheus_client import start_http_server

from .components.asyncloop import AsyncLoop
from .components.baseclass import Base
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
    Base.logger.info(f"Loaded config file: {params}")
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

    AsyncLoop.run(Core(nodes, params).start)


if __name__ == "__main__":
    main()
