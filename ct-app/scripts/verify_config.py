import sys

import click
import yaml

sys.path.insert(1, "./")

from core.components.config_parser import Parameters


@click.command()
@click.option("--file", "-f", type=str, multiple=True, help="Input config file")
def main(file: list[str]):
    result = []
    for f in file:
        with open(f, "r") as stream_file:
            data = yaml.safe_load(stream_file)

        click.echo("Verifying config file: " + f)
        try:
            _ = Parameters.verify(data)
        except KeyError as e:
            click.echo(f"KeyError in {f}: {str(e)}")
            result.append(1)
        except ValueError as e:
            click.echo(f"ValueError in {f}: {str(e)}")
            result.append(1)
        else:
            result.append(0)
    if any(result):
        click.echo("Some config files are invalid.")
        sys.exit(1)
    else:
        click.echo("All config files are valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
