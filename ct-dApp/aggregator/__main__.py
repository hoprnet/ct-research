from functools import partial
from sanic import Sanic
from sanic.worker.loader import AppLoader

from .settings import Settings
from .aggregator import Aggregator
from .setup import create_app


if __name__ == "__main__":
    agg = Aggregator()

    # # start the node and run the event loop until the node stops

    loader = AppLoader(factory=partial(create_app))
    app = loader.load()
    app.prepare(host = Settings.HOST, 
                port = Settings.PORT, 
                dev  = Settings.DEV, 
                fast = Settings.FAST)
    Sanic.serve(primary=app, app_loader=loader)

# send post request:
# curl -X POST http://localhost:8080/list -H "Content-Type: application/json" -d '{"list": [["0x12", 41],["0xF5",95]]}' 

