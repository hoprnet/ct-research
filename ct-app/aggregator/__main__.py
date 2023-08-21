from functools import partial
from tools.db_connection import DatabaseConnection, NodePeerConnection

from sanic import Sanic
from sanic.worker.loader import AppLoader

from tools import envvar, getlogger

from .setup import create_app


def main():
    log = getlogger()

    try:
        envvar("PGHOST")
        envvar("PGPORT", int)
        envvar("PGSSLCERT")
        envvar("PGSSLKEY")
        envvar("PGSSLROOTCERT")
        envvar("PGUSER")
        envvar("PGDATABASE")
        envvar("PGPASSWORD")
        host = envvar("API_HOST")
        port = envvar("API_PORT", int)
    except ValueError:
        log.exception("Error while loading environment variables")
        exit(1)

    with DatabaseConnection(
        envvar("PGDATABASE"),
        envvar("PGHOST"),
        envvar("PGUSER"),
        envvar("PGPASSWORD"),
        envvar("PGPORT", int),
    ) as session:
        session.query(NodePeerConnection).all()
        session.commit()

    loader = AppLoader(factory=partial(create_app))

    app = loader.load()
    app.prepare(host=host, port=port, dev=True)
    Sanic.serve(primary=app, app_loader=loader)


if __name__ == "__main__":
    main()

# send post request:
# curl -X POST http://localhost:8080/list -H "Content-Type: application/json" -d '{"list": [["0x12", 41],["0xF5",95]]}'
