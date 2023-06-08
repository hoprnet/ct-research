import asyncio
import logging
import os
from signal import Signals, SIGINT, SIGTERM
import sys
import traceback
from pathlib import Path
import click

from .exit_codes import ExitCode
from .hopr_node import HOPRNode


def _getlogger(folder: str, filename: str) -> tuple[logging.Logger, str]:
    """
    Returns a logger instance and the name of the log file.
    :param folder: folder to store the log file
    :param filename: name of the log file (without extension)
    """
        
    # configure and get logger handler
    logpath = Path(folder).joinpath(f"{filename}.log")
    logpath.parent.mkdir(parents=True, exist_ok=True)


    # logfile = f"{sys.argv[0]}.log"
    format = "%(levelname)s:%(asctime)s:%(message)s"

    logging.basicConfig(filename=logpath, level=logging.INFO, format=format)
    logger = logging.getLogger(__name__)

    return logger, logpath


def _getenvvar(name: str) -> str:
    """
    Returns the string contained in environment variable 'name' or None.
    """
    if os.getenv(name) is None:
        raise ValueError(f"Environment variable [{name}] not found")

    return os.getenv(name)


def stop(node: HOPRNode, caught_signal: Signals):
    """
    Stops the running node
    """
    click.echo(f">>> Caught signal {caught_signal.name} <<<")
    click.echo(">>> Stopping ...")
    node.stop()


@click.command()
@click.option("--logf", "logfolder", default=".", help="Folder to store the log file")
@click.option("--logn", "logname", default="ct-dApp", help="Name of the log file (w/o ext)")
def main(logfolder: str, logname: str):
    # logger and state variables
    log, logfile = _getlogger(logfolder, logname)
    exit_code = ExitCode.OK

    click.echo(f">>> Program started. Open [ {logfile} ] for logs.")
    click.echo(">>> Press <ctrl+c> to end.")

    # read parameters from environment variables
    try:
        API_host = _getenvvar("HOPR_NODE_1_HTTP_URL")
        API_key = _getenvvar("HOPR_NODE_1_API_KEY")
    except ValueError as e:
        log.error(str(e))
        sys.exit(ExitCode.ERROR_BAD_ARGUMENTS)

    node = HOPRNode(API_host, API_key)

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, stop, node, SIGINT)
    loop.add_signal_handler(SIGTERM, stop, node, SIGTERM)

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
