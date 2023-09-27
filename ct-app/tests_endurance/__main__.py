import json
import os

import click

from . import *  # noqa: F403


@click.command()
@click.option("--file", "configfile", help="Duration of the test in seconds")
def main(configfile: str):
    with open(configfile) as f:
        config: dict = json.load(f)

    scenarios: dict = config.get("scenarios", {})

    for key, value in scenarios.items():
        if "env" in value:
            env: dict = value.get("env", {})

        for k, v in env.items():
            os.environ[k] = str(v)

        for stage in value["stages"]:
            print(f"\033[1m{key}: {value.get('description','')}\033[0m")
            eval(value.get("executor"))(**stage)()

        for k in env.keys():
            del os.environ[k]


if __name__ == "__main__":
    main()
