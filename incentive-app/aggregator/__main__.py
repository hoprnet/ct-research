from functools import partial

import click
from sanic import Sanic
from sanic.worker.loader import AppLoader

from tools import _getlogger

from .aggregator import Aggregator
from .setup import create_app


@click.command()
@click.option("--host", default=None, help="Host to listen on")
@click.option("--port", default=None, type=int, help="Port to listen on")
@click.option("--db", default=None, help="Database to connect to")
@click.option("--dbhost", default=None, help="Database host to connect to")
@click.option("--dbuser", default=None, help="Database user to connect as")
@click.option("--dbpass", default=None, help="Database password to use")
@click.option("--dbport", default=None, type=int, help="Database port to connect to")
def main(
    host: str,
    port: int,
    db: str,
    dbhost: str,
    dbuser: str,
    dbpass: str,
    dbport: int,
):
    log = _getlogger()

    if not host:
        log.error("Host not specified (use --host)")
        exit()
    if not port:
        log.error("Port not specified (use --port)")
        exit()
    if not db:
        log.error("Database not specified (use --db)")
        exit()
    if not dbhost:
        log.error("Database host not specified (use --dbhost)")
        exit()
    if not dbuser:
        log.error("Database user not specified (use --dbuser)")
        exit()
    if not dbpass:
        log.error("Database password not specified (use --dbpassword)")
        exit()
    if not dbport:
        log.error("Database port not specified (use --dbport)")
        exit()

    Aggregator(db, dbhost, dbuser, dbpass, dbport)

    loader = AppLoader(factory=partial(create_app))

    app = loader.load()
    app.prepare(host=host, port=port, dev=True, fast=False)
    Sanic.serve(primary=app, app_loader=loader)


if __name__ == "__main__":
    main()

# send post request:
# curl -X POST http://localhost:8080/list -H "Content-Type: application/json" -d '{"list": [["0x12", 41],["0xF5",95]]}'
