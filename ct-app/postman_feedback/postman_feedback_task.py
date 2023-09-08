from celery import Celery
from tools import envvar, getlogger

from tools.db_connection import DatabaseConnection, Reward


log = getlogger()

app = Celery(name=envvar("PROJECT_NAME"), broker=envvar("CELERY_BROKER_URL"))


@app.task(name="feedback_task")
def feedback_task(
    peer_id: str,
    node_address: str,
    effective_count: int,
    expected_count: int,
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
            expected_count=expected_count,
            effective_count=effective_count,
            status=status,
            timestamp=timestamp,
        )

        session.add(entry)
        session.commit()

        log.debug(f"Stored reward entry in database: {entry}")
