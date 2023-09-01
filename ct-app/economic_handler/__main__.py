import asyncio
from signal import SIGINT, SIGTERM

from tools.exit_codes import ExitCode
from tools.utils import envvar, getlogger

from .economic_handler import EconomicHandler
from .utils_econhandler import stop_instance

log = getlogger()


def main():
    """main"""
    exit_code = ExitCode.OK

    try:
        apihost = envvar("API_HOST")
        apikey = envvar("API_KEY")
        rcphnodes = envvar("RPCH_NODES")
        subgraphurl = envvar("SUBGRAPH_URL")
        envvar("PGHOST")
        envvar("PGPORT", int)
        envvar("PGSSLCERT")
        envvar("PGSSLKEY")
        envvar("PGSSLROOTCERT")
        envvar("PGUSER")
        envvar("PGDATABASE")
        envvar("PGPASSWORD")
        envvar("PGSSLMODE")
        mock_mode = envvar("MOCK_MODE", int)
    except KeyError:
        log.exception("Missing environment variables")
        exit(ExitCode.ERROR_MISSING_ENV_VARS)

    economic_handler = EconomicHandler(
        apihost,
        apikey,
        rcphnodes,
        subgraphurl,
    )

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, stop_instance, economic_handler, SIGINT)
    loop.add_signal_handler(SIGTERM, stop_instance, economic_handler, SIGTERM)

    # start the node and run the event loop until the node stops
    try:
        if mock_mode:
            loop.run_until_complete(economic_handler.mockstart())
        else:
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
