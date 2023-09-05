import asyncio
from signal import SIGINT, SIGTERM

from tools import envvar, getlogger

from .aggregator_trigger import AggregatorTrigger

log = getlogger()


def main():
    try:
        aggregator_url = envvar("AGGREGATOR_URL")
    except ValueError:
        log.exception("Missing environment variables")
        exit()

    instance = AggregatorTrigger(aggregator_url)

    # create the event loop and register the signal handlers
    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, instance.stop)
    loop.add_signal_handler(SIGTERM, instance.stop)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(instance.start())

    except Exception:
        log.exception("Uncaught exception ocurred")
    finally:
        instance.stop()
        loop.close()
        exit()


if __name__ == "__main__":
    main()
