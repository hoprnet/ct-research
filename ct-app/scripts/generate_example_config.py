import sys

import click
import yaml

sys.path.insert(1, "./")

from core.components.config_parser import Parameters


@click.command()
@click.option("--output", "-o", type=str, default="example_config.yaml", help="Output file name")
def main(output: str):
    params = Parameters.generate()
    with open(output, "w") as f:
        yaml.dump(params, f)


if __name__ == "__main__":
    main()
