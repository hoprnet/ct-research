import asyncio
import traceback
from signal import SIGINT, SIGTERM, Signals


from tools import _getlogger, envvar

from .aggregator_trigger import AggregatorTrigger


def stop(trigger: AggregatorTrigger, caught_signal: Signals):
    """
    Stops the running node.
    :param node: the HOPR node to stop
    :param caught_signal: the signal that triggered the stop
    """
    print(f">>> Caught signal {caught_signal.name} <<<")
    print(">>> Stopping ...")
    trigger.stop()


def main():
    log = _getlogger()

    try:
        endpoint = envvar("POST_ENDPOINT")
    except ValueError as e:
        log.error(e)
        exit()

    trigger = AggregatorTrigger(endpoint)

    # create the event loop and register the signal handlers
    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, stop, trigger, SIGINT)
    loop.add_signal_handler(SIGTERM, stop, trigger, SIGTERM)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(trigger.start())

    except Exception as e:
        log.error("Uncaught exception ocurred", str(e))
        log.error(traceback.format_exc())
    finally:
        trigger.stop()
        loop.close()
        exit()


if __name__ == "__main__":
    main()
