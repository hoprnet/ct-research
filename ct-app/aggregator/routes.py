from datetime import datetime

import prometheus_client as prometheus
from sanic import exceptions, response
from sanic.request import Request
from sanic.response import text as sanic_text
from tools.db_connection import DatabaseConnection
from tools.utils import getlogger

from .aggregator import Aggregator


def attach_endpoints(app):
    agg = Aggregator()
    log = getlogger()

    @app.post("/aggregator/peers")
    async def post_peers(request: Request):
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
        if "peers" not in request.json:
            raise exceptions.BadRequest("`peers` key not in body")
        if not isinstance(request.json["peers"], dict):
            raise exceptions.BadRequest("`peers` must be a dict")
        if len(request.json["peers"]) == 0:
            raise exceptions.BadRequest("`peers` must not be empty")

        n_peer = len(request.json["peers"])
        log.info(f"Received update for {n_peer} peers from {request.json['id']}")

        agg.handle_node_peer_latencies(request.json["id"], request.json["peers"])
        agg.set_node_update(request.json["id"], datetime.now())

        return sanic_text("Received peers")

    @app.get("/aggregator/to_db")
    async def post_to_db(request: Request):  # pragma: no cover
        """
        Takes the peers and metrics from the _dict and sends them to the database.
        """
        db_entries = agg.convert_to_db_data()

        if len(db_entries) == 0:
            log.info("No data to send to DB")
            return sanic_text("No data to push to DB")

        with DatabaseConnection() as session:
            session.add_all(db_entries)
            session.commit()

            log.info(f"Inserted {len(db_entries)} rows into DB")

            return sanic_text("Data pushed to DB")

    @app.get("/aggregator/check_timestamps")
    async def check_nodes_timestamps(request: Request):
        """
        Create a GET route to check the last update timestamp for all pods.
        """
        pass

    @app.post("/aggregator/balances")
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

    @app.get("/aggregator/metrics")
    async def metrics(request: Request):
        output = prometheus.exposition.generate_latest().decode("utf-8")
        content_type = prometheus.exposition.CONTENT_TYPE_LATEST

        return response.text(body=output, content_type=content_type)
