from sanic import Sanic

from tools.utils import _getlogger, envvar

from .aggregator import Aggregator
from .middlewares import attach_middlewares
from .routes import attach_endpoints


def create_app():  # pragma: no cover
    log = _getlogger()

    try:
        dbname = envvar("DB_NAME")
        dbhost = envvar("DB_HOST")
        dbuser = envvar("DB_USER")
        dbpass = envvar("DB_PASSWORD")
        dbport = envvar("DB_PORT", int)
    except ValueError as e:
        log.error(e)
        exit(1)

    Aggregator(dbname, dbhost, dbuser, dbpass, dbport)

    try:
        app = Sanic("Aggregator")
        attach_endpoints(app)
        attach_middlewares(app)
    except Exception as e:
        print(e)
        exit

    return app

    # app.run(host = Settings.HOST,
    #         port = Settings.PORT,
    #         dev  = Settings.DEV,
    #         fast = Settings.FAST)
