from functools import partial

import click
from sanic import Sanic
from sanic.worker.loader import AppLoader

from tools import _getlogger

from .aggregator import Aggregator
from .setup import create_app


@click.command()
@click.option("--host", default=None, help="Host to listen on")
@click.option("--port", default=None, help="Port to listen on")
def main(host: str, port: str):
    log = _getlogger()

    if not host:
        log.error("Host not specified (use --host)")
        exit()
    if not port:
        log.error("Port not specified (use --port)")
        exit()

    Aggregator()

    loader = AppLoader(factory=partial(create_app))

    app = loader.load()
    app.prepare(host=host, port=port, dev=True, fast=False)
    Sanic.serve(primary=app, app_loader=loader)


if __name__ == "__main__":
    main()

# send post request:
# curl -X POST http://localhost:8080/list -H "Content-Type: application/json" -d '{"list": [["0x12", 41],["0xF5",95]]}'
