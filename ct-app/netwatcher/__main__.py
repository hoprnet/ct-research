import asyncio
from signal import SIGINT, SIGTERM

from tools.exit_codes import ExitCode
from tools.utils import envvar, getlogger

from .netwatcher import NetWatcher

log = getlogger()


def main():
    exit_code = ExitCode.OK

    try:
        aggpost = envvar("AGG_POST")
        aggbalance = envvar("AGG_BALANCE")
        apihost = envvar("API_HOST")
        apikey = envvar("API_KEY")
        latcount = envvar("LAT_COUNT", int)
        envvar("MOCK_LATENCY", int)
    except KeyError:
        log.exception("Missing environment variables")
        exit(ExitCode.ERROR_MISSING_ENV_VARS)

    instance = NetWatcher(apihost, apikey, aggpost, aggbalance, latcount)

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, instance.stop)
    loop.add_signal_handler(SIGTERM, instance.stop)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(instance.start())

    except Exception:
        log.exception("Uncaught exception ocurred")
        exit_code = ExitCode.ERROR_UNCAUGHT_EXCEPTION

    finally:
        instance.stop()
        loop.close()
        exit(exit_code)


if __name__ == "__main__":
    main()
