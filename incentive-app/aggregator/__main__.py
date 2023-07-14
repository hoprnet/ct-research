from functools import partial

from sanic import Sanic
from sanic.worker.loader import AppLoader
from tools import _getlogger, envvar

from .aggregator import Aggregator
from .setup import create_app


def main():
    log = _getlogger()

    try:
        host = envvar("API_HOST")
        port = envvar("API_PORT", int)

        dbname = envvar("DB_NAME")
        dbhost = envvar("DB_HOST")
        dbuser = envvar("DB_USER")
        dbpass = envvar("DB_PASSWORD")
        dbport = envvar("DB_PORT", int)
    except ValueError as e:
        log.error(e)
        exit(1)

    Aggregator(dbname, dbhost, dbuser, dbpass, dbport)

    loader = AppLoader(factory=partial(create_app))

    app = loader.load()
    app.prepare(host=host, port=port, dev=True, fast=False)
    Sanic.serve(primary=app, app_loader=loader)


if __name__ == "__main__":
    main()

# send post request:
# curl -X POST http://localhost:8080/list -H "Content-Type: application/json" -d '{"list": [["0x12", 41],["0xF5",95]]}'
