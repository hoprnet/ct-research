from datetime import datetime

from sanic import exceptions
from sanic.request import Request
from sanic.response import html as sanic_html
from sanic.response import json as sanic_json
from sanic.response import text as sanic_text

from tools.db_connection.database_connection import DatabaseConnection
from tools.utils import envvar, getlogger

from .aggregator import Aggregator

_db_columns = [
    ("id", "SERIAL PRIMARY KEY"),
    ("peer_id", "VARCHAR(255) NOT NULL"),
    ("node_addresses", "VARCHAR(255)[] NOT NULL"),
    ("latency_metric", "INTEGER[] NOT NULL"),
    ("timestamp", "TIMESTAMP NOT NULL DEFAULT NOW()"),
]


def attach_endpoints(app):
    agg = Aggregator()
    log = getlogger()

    @app.route("/aggregator/list", methods=["POST"])
    async def post_list(request: Request):
        """
        Create a POST route to receive a list of peers from a pod.
        The body of the request must be a JSON object with the following keys:
        - id: the node id
        - list: a list of peers with their latency

        At each call, the list is added to the aggregator, and the last update
        timestamp for the given pod is set to the current time.
        """

        if "id" not in request.json:
            raise exceptions.BadRequest("`id` key not in body")
        if not isinstance(request.json["id"], str):
            raise exceptions.BadRequest("`id` must be a string")
        if "list" not in request.json:
            raise exceptions.BadRequest("`list` key not in body")
        if not isinstance(request.json["list"], dict):
            raise exceptions.BadRequest("`list` must be a dict")
        if len(request.json["list"]) == 0:
            raise exceptions.BadRequest("`list` must not be empty")

        log.info(f"Received list from {request.json['id']}")

        agg.add_node_peer_latencies(request.json["id"], request.json["list"])
        agg.set_node_update(request.json["id"], datetime.now())

        return sanic_text("Received list")

    @app.route("/aggregator/list", methods=["GET"])
    async def get_list(request: Request):
        """
        Create a GET route to retrieve the aggregated list of peers/latency.
        The list is returned as a JSON object with the following keys:
        - id: the node id
        - list: a list of peers with their latency
        """

        log.info("Returned node-peer-latency list")
        return sanic_json(agg.get_node_peer_latencies())

    @app.route("/aggregator/list_ui", methods=["GET"])
    async def get_list_ui(request: Request):  # pragma: no cover
        """
        Create a GET route to retrieve the aggregated list of peers/latency
        and generate an HTML page to display it.
        NO NEED TO CHECK THIS METHOD, AS IT'S PURPOSE IS ONLY FOR DEBUGGING.
        """
        agg_info = agg.get_node_peer_latencies()
        count = len(agg_info)

        # header
        font = "font-family:Source Code Pro;"
        styles = {
            "h1": f"{font}; color: #000050",
            "h2": f"{font}; margin-bottom: 0px; color: #0000b4",
            "date": f"{font}; font-size: small; margin: 0px",
            "line": f"{font}; margin-left: 20px; margin-top: 2px",
        }

        html_text = []
        html_text.append("<body style='background-color: #ffffa0'>")
        html_text.append(f"<h1 style='{styles['h1']}'>Aggregator content</h1>")
        html_text.append(f"<p style='{styles['line']}'>{count} pod(s) detected</p>")

        # peers detected by pods
        for pod_id, data in agg_info.items():
            update_time = agg.get_node_update(pod_id)
            html_text.append(_display_pod_infos(pod_id, data, update_time, styles))

        if len(agg_info) == 0:
            html_text.append(_display_pod_infos("N/A", {}, None, styles))

        action = "location.href='/aggregator/to_db';"
        html_text.append(f"<button type='button' onclick={action}>Send to DB</button>")
        html_text.append("</body>")

        return sanic_html("".join(html_text))

    def _display_pod_infos(
        pod_id: str, data_list: dict, time: datetime, styles: dict
    ):  # pragma: no cover
        """
        Generate the HTML code to display the information of a pod.
        NO NEED TO CHECK THIS METHOD, AS IT'S PURPOSE IS ONLY FOR DEBUGGING.
        """

        def peer_lines(data_list):
            return [f"<b>{peer}</b> ({lat}ms)" for peer, lat in data_list.items()]

        # peer list
        peer_list = ", ".join(peer_lines(data_list)) if len(data_list) != 0 else "N/A"

        # last updated
        timestamp = time.strftime("%d-%m-%Y, %H:%M:%S") if time else "N/A"

        text = []
        text.append(f"<h2 style='{styles['h2']}'>Node ID: {pod_id}</h2>")
        text.append(f"<p style='{styles['date']}'>(Last updated: {timestamp})</p>")

        text.append(f"<p style='{styles['line']}'>Peers: {peer_list}</p>")

        return "".join(text)

    @app.route("/aggregator/to_db", methods=["GET"])
    async def post_to_db(request: Request):  # pragma: no cover
        """
        Takes the peers and metrics from the _dict and sends them to the database.
        """
        matchs_for_db = agg.convert_to_db_data()

        if len(matchs_for_db) == 0:
            log.info("No data to send to DB")
            return sanic_text("No data to push to DB")

        with DatabaseConnection(
            envvar("DB_NAME"),
            envvar("DB_HOST"),
            envvar("DB_USER"),
            envvar("DB_PASSWORD"),
            envvar("DB_PORT", int),
        ) as db:
            try:
                db.create_table("raw_data_table", _db_columns)
            except ValueError as e:
                log.warning(f"Error creating table: {e}")

            if not db.table_exists_guard("raw_data_table"):
                log.error("Table not available, not sending to DB")
                return sanic_text("Table not available", status=500)

            log.info(f"Inserting {len(matchs_for_db)} rows into DB")

            len_data = db.insert_many(
                "raw_data_table",
                ["peer_id", "node_addresses", "latency_metric"],
                matchs_for_db,
            )

            if len_data != len(matchs_for_db):
                log.error("Error inserting into DB")
                return sanic_text("Error inserting into DB", status=500)

            return sanic_text("Data pushed to DB")

    @app.route("/aggregator/balances", methods=["POST"])
    async def post_balance(request: Request):
        """
        Create a POST route to receive the balance of a node.
        """
        if "id" not in request.json:
            raise exceptions.BadRequest("`id` key not in body")
        if not isinstance(request.json["id"], str):
            raise exceptions.BadRequest("`id` must be a string")
        if "balances" not in request.json:
            raise exceptions.BadRequest("`balances` key not in body")
        if not isinstance(request.json["balances"], dict):
            raise exceptions.BadRequest("`balances` must be a dict")

        log.info(f"Received balances from {request.json['id']}")

        for token, amount in request.json["balances"].items():
            agg.add_node_balance(request.json["id"], token, amount)

        return sanic_text(f"Received balance for {request.json['id']}")

    @app.route("/aggregator/metrics", methods=["GET"])
    async def get_metrics(request: Request):
        log.info("Metrics requested")

        return sanic_json(agg.get_metrics())
