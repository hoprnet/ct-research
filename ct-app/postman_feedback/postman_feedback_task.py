from celery import Celery
from tools import envvar, getlogger

from tools.db_connection import DatabaseConnection


_db_columns = [
    ("id", "SERIAL PRIMARY KEY"),
    ("peer_id", "VARCHAR(255) NOT NULL"),
    ("node_address", "VARCHAR(255) NOT NULL"),
    ("expected_count", "INTEGER NOT NULL"),
    ("effective_count", "INTEGER NOT NULL"),
    ("status", "VARCHAR(255) NOT NULL"),
    ("timestamp", "FLOAT NOT NULL"),
]  # will be moved to DatabaseConnection attributes
_table_name = "rewardTable"  # will be moved to DatabaseConnection attributes


log = getlogger()

app = Celery(
    name=envvar("PROJECT_NAME"),
    broker=f"amqp://{envvar('RABBITMQ_USERNAME')}:{envvar('RABBITMQ_PASSWORD')}@{envvar('RABBITMQ_HOST')}/{envvar('RABBITMQ_VIRTUALHOST')}",
    # backend=envvar("CELERY_RESULT_BACKEND"),
)


# the name of the task is the name of the "<task_name>"
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

    with DatabaseConnection(
        envvar("DB_NAME"),
        envvar("DB_HOST"),
        envvar("DB_USER"),
        envvar("DB_PASSWORD"),
        envvar("DB_PORT", int),
    ) as db:
        try:
            db.create_table(_table_name, _db_columns)
        except ValueError as e:
            log.warning(f"Error creating table: {e}")

        if not db.table_exists_guard(_table_name):
            log.error("Table not available, not sending to DB")
            return

        db.insert(
            _table_name,
            peer_id=peer_id,
            node_address=node_address,
            effective_count=effective_count,
            expected_count=expected_count,
            status=status,
            timestamp=timestamp,
        )
        # TODO: once everything merged to dev, here a check should be added to see if
        # insertion is successful
