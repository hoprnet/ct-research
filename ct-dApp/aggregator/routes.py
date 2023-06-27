import copy
from datetime import datetime

import numpy as np
from sanic.request import Request
from sanic.response import html as sanic_html
from sanic.response import text as sanic_text
from sanic.response.convenience import redirect

from db_connection.database_connection import DatabaseConnection

from .aggregator import Aggregator
from .utils import get_best_matchs


def attach_endpoints(app):
    agg = Aggregator()

    @app.route("/aggregator/list", methods=["POST"])
    async def post_list(request: Request):
        """
        Create a POST route to receive a list of peers from a pod.
        The body of the request must be a JSON object with the following keys:
        - id: the network UUID of the pod
        - list: a list of peers with their latency

        At each call, the list is added to the aggregator, and the last update timestamp
        for the given pod is set to the current time.
        """

        if "id" not in request.json:
            return sanic_text("`id` key not in body", status=500)
        if "list" not in request.json:
            return sanic_text("`list` key not in body", status=500)
        
        agg.add(request.json["id"], request.json["list"])
        agg.set_update(request.json["id"], datetime.now())

        return sanic_text("Received list", status=200)
    
    @app.route("/aggregator/list", methods=["GET"])
    async def get_list(request: Request):
        """
        Create a GET route to retrieve the aggregated list of peers/latency and generate 
        an HTML page to display it.
        NO NEED TO CHECK THIS METHOD, AS IT'S PURPOSE IS ONLY FOR DEBUGGING.
        """
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


        action = "location.href='/aggregator/to_db';"
        html_text.append(f"<button type='button' onclick={action}>Send to DB</button>")
        html_text.append("</body>")

        return sanic_html("".join(html_text), status=200)
    

    def _display_pod_infos(pod_id: str, data_list: dict, time: datetime, styles: dict):
        """
        Generate the HTML code to display the information of a pod.
        NO NEED TO CHECK THIS METHOD, AS IT'S PURPOSE IS ONLY FOR DEBUGGING.
        """
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
    
    @app.route("/aggregator/to_db", methods=["GET"])
    async def post_to_db(request: Request):
        """
        Takes the peers and metrics from the _dict and sends them to the database.
        NO NEED TO CHECK THIS METHOD, AS IT'S PURPOSE IS ONLY FOR DEBUGGING.
        """

        # create deep copy of agg._dict using library
        dict_copy = copy.deepcopy(agg._dict)

        nw_names = list(dict_copy.keys())
        peer_names = []

        for _, values in dict_copy.items():
            for peer, _ in values.items():
                if peer not in peer_names:
                    peer_names.append(peer)

        latency_as_array = np.zeros((len(nw_names), len(peer_names)), dtype=np.int32)
        for nw_idx, values in enumerate(dict_copy.values()):
            for peer, lat in values.items():
                peer_idx = peer_names.index(peer)
                latency_as_array[nw_idx, peer_idx] = int(lat)


        matchs = get_best_matchs(latency_as_array, max_iter=3)

        matchs_for_db = []
        for peer_idx, nw_idxs in matchs.items():
            peer = peer_names[peer_idx]
            nws = [nw_names[idx] for idx in nw_idxs]
            latencies = [int(latency_as_array[idx, peer_idx]) for idx in nw_idxs]

            matchs_for_db.append((peer, nws, latencies))

        
        with DatabaseConnection(database="metricDB",
                                host="localhost",
                                user="postgres",
                                password="admin",
                                port="5432") as db:
            for peer, nws, latencies in matchs_for_db:
                db.insert("raw_data_table", 
                          peer=peer, 
                          nws=nws,
                          latencies=latencies)

        return redirect('/aggregator/list')