import asyncio
from signal import SIGINT, SIGTERM, Signals


from tools.exit_codes import ExitCode
from tools.utils import getlogger, envvar

from .netwatcher import NetWatcher

log = getlogger()


def stop(instance: NetWatcher, caught_signal: Signals):
    """
    Stops the running node.
    :param node: the HOPR node to stop
    :param caught_signal: the signal that triggered the stop
    """
    log.info(f">>> Caught signal {caught_signal.name} <<<")
    log.info(">>> Stopping ...")
    instance.stop()


def main():
    exit_code = ExitCode.OK

    try:
        aggpost = envvar("AGG_POST")
        aggbalance = envvar("AGG_BALANCE")
        apihost = envvar("API_HOST")
        apikey = envvar("API_KEY")
        latcount = envvar("LAT_COUNT", int)
        mock_mode = envvar("MOCK_MODE", bool)
    except KeyError:
        log.exception("Missing environment variables")
        exit(ExitCode.ERROR_MISSING_ENV_VARS)

    nw = NetWatcher(apihost, apikey, aggpost, aggbalance, latcount)
    nw.mock_mode = mock_mode

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, stop, nw, SIGINT)
    loop.add_signal_handler(SIGTERM, stop, nw, SIGTERM)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(nw.start())

    except Exception:
        log.exception("Uncaught exception ocurred")
        exit_code = ExitCode.ERROR_UNCAUGHT_EXCEPTION

    finally:
        nw.stop()
        loop.close()
        exit(exit_code)


if __name__ == "__main__":
    main()
