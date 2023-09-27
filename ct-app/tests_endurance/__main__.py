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
    num_scenarios = len(scenarios)

    for scenario_idx, (key, value) in enumerate(scenarios.items()):
        if "env" in value:
            env: dict = value.get("env", {})

        for k, v in env.items():
            os.environ[k] = str(v)

        print("\033[1m", end="")
        print(
            f"[{scenario_idx+1}/{num_scenarios}] {key}: {value.get('description','')}",
            end="",
        )
        print("\033[0m")

        len(value["stages"])
        for stage_idx, stage in enumerate(value["stages"]):
            print("\033[1m", end="")
            print(f"  [+] stage {stage_idx+1}/{len(value['stages'])}", end="")
            print("\033[0m")
            eval(value.get("executor"))(**stage)()

        for k in env.keys():
            del os.environ[k]


if __name__ == "__main__":
    main()
