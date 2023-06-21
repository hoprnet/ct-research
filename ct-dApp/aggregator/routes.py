from sanic.response import text as sanic_text
from aggregator import Aggregator

def setup_routes(app):
    agg = Aggregator()

    @app.route("/aggregator/list", methods=["POST"])
    async def post_list(request):
        if "list" not in request.json:
            return sanic_text("Bad content")
        
        data_list = request.json["list"]
        agg.add(data_list)

        return sanic_text(f"Received information for {len(data_list)} peers")
    
    @app.route("/aggregator/list", methods=["GET"])
    async def get_list(request):
        print(f"GET {agg.get()=}")
        return sanic_text("Hello world")