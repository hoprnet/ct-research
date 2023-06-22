from sanic.response import html as sanic_html
from sanic.response import text as sanic_text

from aggregator import Aggregator
from datetime import datetime

def setup_routes(app):
    agg = Aggregator()

    @app.route("/aggregator/list", methods=["POST"])
    async def post_list(request):
        if "id" not in request.json:
            return sanic_text("`id` key not in body", status=500)
        if "list" not in request.json:
            return sanic_text("`list` key not in body", status=500)
        
        agg.add(request.json["id"], request.json["list"])
        agg.set_update(datetime.now())
        return sanic_text("Received list", status=200)
    
    @app.route("/aggregator/list", methods=["GET"])
    async def get_list(request):

        # header
        style = "style='font-family:Source Code Pro;'"
        html_text = f"<h1 {style}>Aggregated List</h1>"

        # last updated
        timestamp = "N/A"
        if time := agg.get_update():
            timestamp = time.strftime("%d-%m-%Y, %H:%M:%S")

        html_text += f"<p {style}>Last updated: {timestamp}</p>"

        # peers detected by pods
        for pod_id, data_list in agg.get().items():
            html_text += f"<h2 {style}>NW UUID: {pod_id}</h2>"
            html_text += f"<p {style}>&ensp;Seen peers: {', '.join(data_list)}</p>"

        return sanic_html(html_text, status=200)
