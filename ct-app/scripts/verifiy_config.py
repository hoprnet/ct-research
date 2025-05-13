import sys

import click
import yaml

sys.path.insert(1, "./")

from core.components.config_parser import Parameters


@click.command()
@click.option("--input", "-i", type=str, help="Input config file")
def main(input: str):

    with open(input, "r") as f:
        data = yaml.safe_load(f)

    try:
        _ = Parameters.verify(data)
    except KeyError as e:
        click.echo(f"KeyError: {e}")
        return 1
    except ValueError as e:
        click.echo(f"ValueError: {e}")
        return 1
    else:
        click.echo("Config file is valid.")
        return 0


if __name__ == "__main__":
    main()
