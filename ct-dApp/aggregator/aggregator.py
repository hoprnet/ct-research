from sanic import Sanic
from sanic.response import text as sanic_text
from sanic.views import HTTPMethodView

app = Sanic("__name__")

class Aggregator(HTTPMethodView):
    async def post(self, request):
        if "list" not in request.json:
            return sanic_text("Bad content")
        
        data_list = request.json["list"]
        return sanic_text(f"Received information for {len(data_list)} peers")


app.add_route(Aggregator.as_view(), "/list")

if __name__ == '__main__':
    app.run(dev=True)

# send post request:
# curl -X POST http://localhost:8000/list -H "Content-Type: application/json" -d '{"list": [["0x12", 41],["0xF5",95]]}' 

