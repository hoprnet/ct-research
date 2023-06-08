import logging
import os
from pathlib import Path
from signal import Signals

import click

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