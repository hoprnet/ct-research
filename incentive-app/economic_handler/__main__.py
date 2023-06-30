import asyncio
from signal import SIGINT, SIGTERM, Signals

from tools.exit_codes import ExitCode
from tools.utils import _getenvvar
from .economic_handler import EconomicHandler


def stop(instance: EconomicHandler, signal: Signals):
    """Stop the economic handler instance when a signal is received"""
    print(f">>> Caught signal {signal.name} <<<")
    instance.stop()


def main():
    """main"""
    try:
        API_host = _getenvvar("HOPR_NODE_1_HTTP_URL")
        API_key = _getenvvar("HOPR_NODE_1_API_KEY")
        RPCH_nodes = _getenvvar("RPCH_NODES_API_ENDPOINT")
    except ValueError:
        exit(ExitCode.ERROR_BAD_ARGUMENTS)

    economic_handler = EconomicHandler(API_host, API_key, RPCH_nodes)

    # tasks = [
    #     economic_handler.channel_topology(),
    #     economic_handler.read_parameters_and_equations(),
    #     economic_handler.blacklist_rpch_nodes(api_endpoint=RPCH_nodes),
    # ]

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
