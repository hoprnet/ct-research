import asyncio
from signal import SIGINT, SIGTERM

from ct.exit_codes import ExitCode
from ct.utils import _getlogger, stop
import click

from .netwatcher import NetWatcher

@click.command()
@click.option("--port", "port", help="Port to specify the node")
@click.option("--apihost", "apihost", help="API host to specify the node")
@click.option("--apikey", "apikey", help="API key to specify the node")
@click.option("--aggpost", "aggpost", help="AGG post route to specify the node")
def main(port: str, apihost: str, apikey: str, aggpost: str):
    log = _getlogger()
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