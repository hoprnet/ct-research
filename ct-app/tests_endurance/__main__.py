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

    scenarios_results = []
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
        stage_results = []
        for stage_idx, stage in enumerate(stages, 1):
            EnduranceTest.bold(f"stage [{stage_idx}/{num_stages}]", prefix="\t")

            try:
                success = eval(value.get("executor"))(**stage)()
            except Exception as e:
                EnduranceTest.error(f"{e.__class__.__name__}: {e}", prefix="\t")
                success = False

            stage_results.append(success)
            display_success(success)

        successful_stages = sum(stage_results)
        scenarios_results.append(successful_stages == num_stages)

        display_results(successful_stages, num_stages, "test")

        del_envvars(env.keys())

    successful_scenarios = sum(scenarios_results)
    print("." * 45)
    display_results(successful_scenarios, num_scenarios, "scenario")

    del_envvars(["LOG_LEVEL", "LOG_ENABLED"])
    del_envvars(global_env.keys())


def display_success(success: bool):
    if success:
        EnduranceTest.success("Test successful", prefix="\t", end="\n" * 2)
    else:
        EnduranceTest.error("Test failed", prefix="\t", end="\n" * 2)


def display_results(hit: int, total: int, element: str):
    if hit == total:
        method = EnduranceTest.success
    elif hit > 0:
        method = EnduranceTest.warning
    else:
        method = EnduranceTest.error

    plural = "s" if hit > 1 else ""

    method(f"{hit}/{total} {element}{plural} passed", end="\n" * 2)


if __name__ == "__main__":
    main()
