import asyncio
from signal import SIGINT, SIGTERM, Signals


from tools import getlogger, envvar

from .aggregator_trigger import AggregatorTrigger

log = getlogger()


def stop(trigger: AggregatorTrigger, caught_signal: Signals):
    """
    Stops the running node.
    :param node: the HOPR node to stop
    :param caught_signal: the signal that triggered the stop
    """
    log.info(f">>> Caught signal {caught_signal.name} <<<")
    log.info(">>> Stopping ...")
    trigger.stop()


def main():
    try:
        endpoint = envvar("POST_TO_DB_ENDPOINT")
    except ValueError:
        log.exception("Missing environment variables")
        exit()

    trigger = AggregatorTrigger(endpoint)

    # create the event loop and register the signal handlers
    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, stop, trigger, SIGINT)
    loop.add_signal_handler(SIGTERM, stop, trigger, SIGTERM)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(trigger.start())

    except Exception:
        log.exception("Uncaught exception ocurred")
    finally:
        trigger.stop()
        loop.close()
        exit()


if __name__ == "__main__":
    main()
