from sanic.response import html as sanic_html
from sanic.response import text as sanic_text
from sanic.request import Request

from aggregator import Aggregator
from datetime import datetime

def setup_routes(app):
    agg = Aggregator()

    @app.route("/aggregator/list", methods=["POST"])
    async def post_list(request: Request):
        if "id" not in request.json:
            return sanic_text("`id` key not in body", status=500)
        if "list" not in request.json:
            return sanic_text("`list` key not in body", status=500)
        
        agg.add(request.json["id"], request.json["list"])
        agg.set_update(request.json["id"], datetime.now())

        return sanic_text("Received list", status=200)
    
    @app.route("/aggregator/list", methods=["GET"])
    async def get_list(request: Request):
        agg_info = agg.get()
        count = len(agg_info)

        # header
        font = "font-family:Source Code Pro;"
        styles = {
            "h1":   f"{font}; color: #000050",
            "h2":   f"{font}; margin-bottom: 0px; color: #0000b4",
            "date": f"{font}; font-size: small; margin: 0px",
            "line": f"{font}; margin-left: 20px; margin-top: 2px"
        }

        html_text = []
        html_text.append("<body style='background-color: #ffffa0'>")
        html_text.append(f"<h1 style='{styles['h1']}'>Aggregator content</h1>")
        html_text.append(f"<p style='{styles['line']}'>{count} pod(s) detected</p>")

        # peers detected by pods
        for pod_id, data in agg_info.items():
            update_time = agg.get_update(pod_id)
            html_text.append(_display_pod_infos(pod_id, data, update_time, styles))

        if len(agg_info) == 0:
            html_text.append(_display_pod_infos("N/A", {}, None, styles))

        html_text.append("</body>")

        return sanic_html("".join(html_text), status=200)
    

    def _display_pod_infos(pod_id: str, data_list: dict, time: datetime, styles: dict):
        def peer_lines(data_list):
            return [f"<b>{peer}</b> ({lat}ms)" for peer, lat in data_list.items()]
        # peer list
        peer_list = ', '.join(peer_lines(data_list)) if len(data_list) != 0 else "N/A"

        # last updated
        timestamp = time.strftime("%d-%m-%Y, %H:%M:%S") if time else "N/A"

        text = []
        text.append(f"<h2 style='{styles['h2']}'>NW UUID: {pod_id}</h2>")
        text.append(f"<p style='{styles['date']}'>(Last updated: {timestamp})</p>")

        text.append(f"<p style='{styles['line']}'>Peers: {peer_list}</p>")

        return ''.join(text)