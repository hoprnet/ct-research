import asyncio
from signal import SIGINT, SIGTERM

from prometheus_client import start_http_server

from tools.exit_codes import ExitCode
from tools.utils import envvar, getlogger

from .economic_handler import EconomicHandler

log = getlogger()


def main():
    """main"""
    exit_code = ExitCode.OK

    try:
        apihost = envvar("API_HOST")
        apikey = envvar("API_KEY")
        rcphnodes = envvar("RPCH_NODES")
        subgraphurl = envvar("SUBGRAPH_URL")
        min_database_entries = envvar("MIN_DATABASE_ENTRIES", int)
        envvar("PARAMETER_FILE")
        envvar("PGHOST")
        envvar("PGPORT", int)
        envvar("PGSSLCERT")
        envvar("PGSSLKEY")
        envvar("PGSSLROOTCERT")
        envvar("PGUSER")
        envvar("PGDATABASE")
        envvar("PGPASSWORD")
        envvar("PGSSLMODE")
        envvar("TASK_NAME")
    except KeyError:
        log.exception("Missing environment variables")
        exit(ExitCode.ERROR_MISSING_ENV_VARS)

    instance = EconomicHandler(
        apihost, apikey, rcphnodes, subgraphurl, min_database_entries
    )

    loop = asyncio.new_event_loop()
    loop.add_signal_handler(SIGINT, instance.stop)
    loop.add_signal_handler(SIGTERM, instance.stop)

    # start the prometheus client
    start_http_server(8080)

    # start the node and run the event loop until the node stops
    try:
        loop.run_until_complete(instance.start())
    except Exception as e:
        print("Uncaught exception ocurred", str(e))
        exit_code = ExitCode.ERROR_UNCAUGHT_EXCEPTION

    finally:
        instance.stop()
        loop.close()
        exit(exit_code)


if __name__ == "__main__":
    main()
