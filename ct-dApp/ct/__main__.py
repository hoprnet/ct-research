import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path
from signal import SIGINT, SIGTERM, Signals

import click

from .exit_codes import ExitCode
from .hopr_node import HOPRNode


def _getlogger(folder: str, filename: str) -> logging.Logger:
    """
    Generate a logger instance based on folder and name.
    :param folder: folder to store the log file
    :param filename: name of the log file (without extension)
    :returns: a tuple with the logger instance and the name of the log file
    """
        
    # configure and get logger handler
    logpath = Path(folder).joinpath(f"{filename}.log")
    logpath.parent.mkdir(parents=True, exist_ok=True)
    format = "%(levelname)s:%(asctime)s:%(message)s"

    logging.basicConfig(filename=logpath, level=logging.INFO, format=format)
    logger = logging.getLogger(__name__)

    return logger


def _getenvvar(name: str) -> str:
    """
    Gets the string contained in environment variable 'name'.
    :param name: name of the environment variable
    :returns: the string contained in the environment variable
    :raises ValueError: if the environment variable is not found
    """
    if os.getenv(name) is None:
        raise ValueError(f"Environment variable [{name}] not found")

    return os.getenv(name)


def stop(node: HOPRNode, caught_signal: Signals):
    """
    Stops the running node.
    :param node: the HOPR node to stop
    :param caught_signal: the signal that triggered the stop
    """
    click.echo(f">>> Caught signal {caught_signal.name} <<<")
    click.echo(">>> Stopping ...")
    node.stop()

@click.command()
@click.option("--logf", "logfolder", default=".", help="Folder to store the log file")
@click.option("--logn", "logname", default="ct-dApp", help="Name of the log file")
@click.option("--latcount", "latency_count", default=100, help="Nb of latency measures to store")
def main(logfolder: str, logname: str, latency_count: int):
    # logger and state variables
    log = _getlogger(logfolder, logname)
    exit_code = ExitCode.OK

    click.echo(f">>> Program started. Open [ {logfolder} ] for logs.")
    click.echo(">>> Press <ctrl+c> to end.")

    # read parameters from environment variables
    try:
        API_host = _getenvvar("HOPR_NODE_1_HTTP_URL")
        API_key = _getenvvar("HOPR_NODE_1_API_KEY")
    except ValueError as e:
        log.error(str(e))
        sys.exit(ExitCode.ERROR_BAD_ARGUMENTS)

    # create the HOPR node instance
    node = HOPRNode(API_host, API_key, latency_count, logfolder)

    # create the event loop and register the signal handlers
    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, stop, node, SIGINT)
    loop.add_signal_handler(SIGTERM, stop, node, SIGTERM)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(node.start())

    except Exception as e:
        log.error("Uncaught exception ocurred", str(e))
        log.error(traceback.format_exc())
        exit_code = ExitCode.ERROR_UNCAUGHT_EXCEPTION

    finally:
        node.stop()
        loop.close()
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
