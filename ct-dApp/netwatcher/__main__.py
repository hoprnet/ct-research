import asyncio
from signal import SIGINT, SIGTERM

from ct.exit_codes import ExitCode
from ct.utils import _getenvvar, _getlogger, stop
import click

from .netwatcher import NetWatcher

@click.command()
@click.option("--port", "port", help="Port to specify the node")
def main(port: str):
    log = _getlogger()
    exit_code = ExitCode.OK
    
    try:
        API_host = _getenvvar("HOPR_NODE_HTTP_URL").replace("PORT_FIELD", port)
        API_key = _getenvvar("HOPR_NODE_API_KEY").replace("PORT_FIELD", port)
        AGG_post_route = _getenvvar("AGG_HTTP_POST_URL")
    except ValueError:
        exit(ExitCode.ERROR_BAD_ARGUMENTS)
        
    nw = NetWatcher(API_host, API_key, AGG_post_route)

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