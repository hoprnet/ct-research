from sanic import Sanic
from tools import getlogger

from .aggregator import Aggregator
from .middlewares import attach_middlewares
from .routes import attach_endpoints

log = getlogger()


def create_app():  # pragma: no cover
    agg = Aggregator()  # noqa: F841

    try:
        app = Sanic("Aggregator")
        attach_endpoints(app)
        attach_middlewares(app)
    except Exception:
        log.exception("Error while creating app")
        exit()

    return app

    # app.run(host = Settings.HOST,
    #         port = Settings.PORT,
    #         dev  = Settings.DEV,
    #         fast = Settings.FAST)
