import logging
from datetime import datetime

from celery import Celery
from core.components.parameters import Parameters
from db_connection import DatabaseConnection, Reward

log = logging.getLogger()

params = Parameters()(env_prefix="PARAM_")

app = Celery(name=params.celery_project_name, broker=params.celery_broker_url)
app.autodiscover_tasks(force=True)


@app.task(name="feedback_task")
def feedback_task(
    peer_id: str,
    node_address: str,
    expected: int,
    issued: int,
    relayed: int,
    status: str,
    timestamp: float,
):
    """
    Celery task to store the message delivery status in the database.
    """

    with DatabaseConnection() as session:
        entry = Reward(
            peer_id=peer_id,
            node_address=node_address,
            expected_count=expected,
            effective_count=relayed,
            status=status,
            timestamp=datetime.fromtimestamp(timestamp),
            issued_count=issued,
        )

        session.add(entry)
        session.commit()

        log.debug(f"Stored reward entry in database: {entry}")
