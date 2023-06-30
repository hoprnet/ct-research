from sanic import Sanic

from .middlewares import attach_middlewares
from .routes import attach_endpoints


def create_app():    
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

