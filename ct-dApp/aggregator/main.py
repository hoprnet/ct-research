from sanic import Sanic
from settings import Settings
from routes import setup_routes
from middlewares import setup_middlewares
from aggregator import Aggregator

app = Sanic("Aggregator")
agg = Aggregator()
setup_routes(app)
setup_middlewares(app)


if __name__ == '__main__':
    app.run(host = Settings.HOST, 
            port = Settings.PORT, 
            dev  = Settings.DEV, 
            fast = Settings.FAST)

# send post request:
# curl -X POST http://localhost:8080/list -H "Content-Type: application/json" -d '{"list": [["0x12", 41],["0xF5",95]]}' 

