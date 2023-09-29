import yaml
import os

import click

from . import *  # noqa: F403
from . import EnduranceTest


def set_envvars(pairs: list[tuple[str, str]]):
    if isinstance(pairs, tuple):
        pairs = [pairs]

    for name, value in pairs:
        os.environ[name] = str(value)


def del_envvars(names: str or list[str]):
    if isinstance(names, str):
        names = [names]

    for name in names:
        del os.environ[name]


@click.command()
@click.option("--file", "configfile")
def main(configfile: str):
    with open(configfile) as f:
        config: dict = yaml.safe_load(f)

    scenarios: dict[str, dict] = config.get("scenarios", {})

    # logs variables
    logs: dict = config.get("logs", {})
    set_envvars(("LOG_LEVEL", logs.get("level", "INFO")))
    set_envvars(("LOG_ENABLED", logs.get("enabled", False)))

    # env variables
    global_env: dict = config.get("global_env", {})
    set_envvars(global_env.items())

    num_scenarios = len(scenarios)

    for scenario_idx, (key, value) in enumerate(scenarios.items()):
        env: dict = value.get("env", {})

        set_envvars(env.items())

        EnduranceTest.bold(
            f"{key} [{scenario_idx+1}/{num_scenarios}]: {value.get('description','')}"
        )
        if not value.get("execute", True):
            EnduranceTest.warning("SKIPPED", prefix="\t")
            continue

        stages = value.get("stages", [])
        num_stages = len(stages)
        for stage_idx, stage in enumerate(stages, 1):
            EnduranceTest.bold(f"stage [{stage_idx}/{num_stages}]", prefix="\t")

            eval(value.get("executor"))(**stage)()

        del_envvars(env.keys())

    del_envvars(["LOG_LEVEL", "LOG_ENABLED"])
    del_envvars(global_env.keys())


if __name__ == "__main__":
    main()
