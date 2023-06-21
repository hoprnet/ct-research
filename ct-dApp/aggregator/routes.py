from sanic.response import text as sanic_text
from aggregator import Aggregator

def setup_routes(app):
    agg = Aggregator()

    @app.route("/aggregator/list", methods=["POST"])
    async def post_list(request):
        if "id" not in request.json:
            return sanic_text("`id` key not in body", status=500)
        if "list" not in request.json:
            return sanic_text("`list` key not in body", status=500)
        
        pod_id = request.json["id"]
        data_list = request.json["list"]
        
        agg.add({pod_id: data_list})

        return sanic_text(f"Received list of length {len(data_list)}", status=200)
    
    @app.route("/aggregator/list", methods=["GET"])
    async def get_list(request):
        return sanic_text(f"{agg.get()}", status=200)