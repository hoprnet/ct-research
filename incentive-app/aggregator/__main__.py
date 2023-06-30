from functools import partial
from sanic import Sanic
from sanic.worker.loader import AppLoader
import click

from .settings import Settings
from .aggregator import Aggregator
from .setup import create_app

@click.command()
@click.option('--host', default=Settings.HOST, help='Host to listen on')
@click.option('--port', default=Settings.PORT, help='Port to listen on')
def main(host: str, port: str):
    Aggregator()

    loader = AppLoader(factory=partial(create_app))

    app = loader.load()
    app.prepare(host = host,
                port = port,
                dev  = True, 
                fast = False)
    Sanic.serve(primary=app, app_loader=loader)

if __name__ == "__main__":
    main()

# send post request:
# curl -X POST http://localhost:8080/list -H "Content-Type: application/json" -d '{"list": [["0x12", 41],["0xF5",95]]}' 

