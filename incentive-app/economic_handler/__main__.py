import asyncio
from signal import SIGINT, SIGTERM, Signals

import click

from tools.exit_codes import ExitCode
from tools.utils import _getlogger
from .economic_handler import EconomicHandler


def stop(instance: EconomicHandler, signal: Signals):
    """Stop the economic handler instance when a signal is received"""
    print(f">>> Caught signal {signal.name} <<<")
    instance.stop()


@click.command()
@click.option("--port", default=None, help="Port specifying the node")
@click.option("--apihost", default=None, help="IP-address of the API host")
@click.option("--apikey", default=None, help="API key of the API host")
@click.option("--rcphnodes", default=None, help="API endpoint for RPCh nodes")
def main(port: str, apihost: str, apikey: str, rcphnodes: str):
    """main"""
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
    if not rcphnodes:
        log.error("Endpoint for RPCh nodes not specified (use --rcphnodes)")
        exit()

    exit_code = ExitCode.OK

    economic_handler = EconomicHandler(f"http://{apihost}:{port}", apikey, rcphnodes)

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, stop, economic_handler, SIGINT)
    loop.add_signal_handler(SIGTERM, stop, economic_handler, SIGTERM)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(economic_handler.start())

    except Exception as e:
        print("Uncaught exception ocurred", str(e))
        exit_code = ExitCode.ERROR_UNCAUGHT_EXCEPTION

    finally:
        economic_handler.stop()
        loop.close()
        exit(exit_code)


if __name__ == "__main__":
    main()
