import asyncio
import sys
import traceback
from signal import SIGINT, SIGTERM

import click

from .exit_codes import ExitCode
from .hopr_node import HOPRNode
from .utils import _getenvvar, _getlogger, stop


@click.command()
@click.option("--plotf", "plotfolder", default=".", help="Folder to store the plots")
@click.option("--latcount", "latency_count", default=100, help="Nb of latency measures to store")
def main(plotfolder: str, latency_count: int):
    # logger and state variables
    log = _getlogger()
    exit_code = ExitCode.OK

    click.echo(">>> Program started.")
    click.echo(">>> Press <ctrl+c> to end.")

    # read parameters from environment variables
    try:
        API_host = _getenvvar("HOPR_NODE_1_HTTP_URL")
        API_key = _getenvvar("HOPR_NODE_1_API_KEY")
    except ValueError as e:
        log.error(str(e))
        sys.exit(ExitCode.ERROR_BAD_ARGUMENTS)

    # create the HOPR node instance
    node = HOPRNode(API_host, API_key, latency_count, plotfolder)

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
