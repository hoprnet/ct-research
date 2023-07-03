import asyncio
from signal import SIGINT, SIGTERM

import click

from tools.exit_codes import ExitCode
from tools.utils import _getlogger, stop

from .netwatcher import NetWatcher


@click.command()
@click.option("--port", default=None, help="Port to specify the node")
@click.option("--apihost", default=None, help="API host to specify the node")
@click.option("--apikey", default=None, help="API key to specify the node")
@click.option("--aggpost", default=None, help="AGG post route to specify the node")
def main(port: str, apihost: str, apikey: str, aggpost: str):
    log = _getlogger()

    if not port:
        log.error("Port not specified (use --port)")
        exit()
    if not apihost:
        log.error("API host not specified (use --apihost)")
        exit()
    if not apikey:
        log.error("API key not specified (use --apikey)")
        exit()
    if not aggpost:
        log.error("Aggregator post route not specified (use --aggpost)")
        exit()

    exit_code = ExitCode.OK

    nw = NetWatcher(f"http://{apihost}:{port}", apikey, aggpost)

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, stop, nw, SIGINT)
    loop.add_signal_handler(SIGTERM, stop, nw, SIGTERM)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(nw.start())

    except Exception as e:
        log.error("Uncaught exception ocurred", str(e))
        exit_code = ExitCode.ERROR_UNCAUGHT_EXCEPTION

    finally:
        nw.stop()
        loop.close()
        exit(exit_code)


if __name__ == "__main__":
    main()
