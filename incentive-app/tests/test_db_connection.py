from datetime import datetime, timedelta
from tools.db_connection import DatabaseConnection  # noqa: F401
import pytest
import time


@pytest.fixture
def db_fixture():
    """
    Fixture for DatabaseConnection instance.
    """
    instance = DatabaseConnection(
        database="metricDB",
        host="localhost",
        user="postgres",
        password="admin",
        port="5432",
    )
    yield instance


@pytest.fixture
def cols_fixture():
    """
    Fixture for columns list.
    """
    columns = [
        ("id", "SERIAL PRIMARY KEY"),
        ("peer_id", "VARCHAR(255) NOT NULL"),
        ("node_addresses", "VARCHAR(255)[] NOT NULL"),
        ("latency_metric", "INTEGER[] NOT NULL"),
        ("timestamp", "TIMESTAMP NOT NULL DEFAULT NOW()"),
    ]
    yield columns


def test_db_connection(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection connection.
    """
    with db_fixture as db:
        assert db.conn is not None

    assert db_fixture is not None


def test_create_table(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection create_table
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        assert db.table_exists_guard("test_table")


def test_drop_table(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection drop_table
    """
    with db_fixture as db:
        db.drop_table("test_table")
        assert not db.table_exists_guard("test_table")


def test_column_exists_guard(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection column_exists_guard method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        assert db.column_exists_guard("test_table", cols_fixture[0][0])
        assert not db.column_exists_guard("test_table", cols_fixture[0][0] + "foo")

        db.drop_table("test_table")


def test_non_default_columns(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection test_get_non_default_columns method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        assert db.non_default_columns("test_table") == [
            col[0] for col in cols_fixture[1:-1]
        ]
        db.drop_table("test_table")


def test_insert(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection insert method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert(
            "test_table",
            peer_id="0xF514",
            node_addresses=["0xF24", "0xF21"],
            latency_metric=[100, 13],
        )
        db.drop_table("test_table")


def test_insert_unknown_column(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection insert method with unknown column.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        with pytest.raises(ValueError):
            db.insert(
                "test_table",
                peer_id="0xF514",
                node_addresses=["0xF24", "0xF21"],
                latency_metric=[100, 13],
                foo="bar",
            )
        db.drop_table("test_table")


def test_insert_missing_column(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection insert method with missing column.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        with pytest.raises(ValueError):
            db.insert(
                "test_table",
                peer_id="0xF514",
                node_addresses=["0xF24", "0xF21"],
            )
        db.drop_table("test_table")


def test_insert_many(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection insert_many method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF516", ["0xF24", "0xF21"], [100, 13]),
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
                ("0xF518", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        db.drop_table("test_table")


def test_insert_many_unknown_column(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection insert_many method with unknown column.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        with pytest.raises(ValueError):
            db.insert_many(
                "test_table",
                ["peer_id", "node_addresses", "latency_metric", "foo"],
                [
                    ("0xF516", ["0xF24", "0xF21"], [100, 13], "bar"),
                    ("0xF517", ["0xF24", "0xF21"], [100, 13], "bar"),
                    ("0xF518", ["0xF24", "0xF21"], [100, 13], "bar"),
                    ("0xF519", ["0xF24", "0xF21"], [100, 13], "bar"),
                ],
            )
        db.drop_table("test_table")


def test_insert_many_missing_column(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection insert_many method with missing column.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        with pytest.raises(ValueError):
            db.insert_many(
                "test_table",
                ["peer_id", "node_addresses"],
                [
                    ("0xF516", ["0xF24", "0xF21"], [100, 13]),
                    ("0xF517", ["0xF24", "0xF21"], [100, 13]),
                    ("0xF518", ["0xF24", "0xF21"], [100, 13]),
                    ("0xF519", ["0xF24", "0xF21"], [100, 13]),
                ],
            )
        db.drop_table("test_table")


def test_last_row(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection last_row method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert(
            "test_table",
            peer_id="0xF514",
            node_addresses=["0xF24", "0xF21"],
            latency_metric=[100, 13],
        )
        last_row = db.last_row("test_table")
        db.drop_table("test_table")

        assert last_row[1:-1] == ("0xF514", ["0xF24", "0xF21"], [100, 13])


def test_last_row_empty(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection last_row method with empty table.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        last_row = db.last_row("test_table")
        db.drop_table("test_table")

        assert last_row is None


def test_row(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection row method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert(
            "test_table",
            peer_id="0xF514",
            node_addresses=["0xF24", "0xF21"],
            latency_metric=[100, 13],
        )
        row = db.row("test_table", 1)
        db.drop_table("test_table")

        assert row[1:-1] == ("0xF514", ["0xF24", "0xF21"], [100, 13])


def test_row_empty(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection row method with empty table.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        row = db.row("test_table", 1)
        db.drop_table("test_table")

        assert row is None


def test_last_added_rows(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection last_added_rows method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF516", ["0xF24", "0xF21"], [100, 13]),
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF518", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
                ("0xF520", ["0xF24", "0xF21"], [100, 13]),
                ("0xF521", ["0xF24", "0xF21"], [100, 13]),
                ("0xF522", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        rows = db.last_added_rows("test_table")
        db.drop_table("test_table")

        assert len(rows) == 5
        assert rows[0][1] == "0xF518"
        assert rows[1][1] == "0xF519"
        assert rows[2][1] == "0xF520"
        assert rows[3][1] == "0xF521"
        assert rows[4][1] == "0xF522"


def test_last_added_rows_empty(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection last_added_rows method with empty table.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        rows = db.last_added_rows("test_table")
        db.drop_table("test_table")

        assert rows is None


def test_count_last_added_rows(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection count_last_added_rows method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF516", ["0xF24", "0xF21"], [100, 13]),
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF518", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
                ("0xF520", ["0xF24", "0xF21"], [100, 13]),
                ("0xF521", ["0xF24", "0xF21"], [100, 13]),
                ("0xF522", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        count = db.count_last_added_rows("test_table")
        db.drop_table("test_table")

        assert count == 5


def test_count_last_added_rows_empty(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection count_last_added_rows method with empty table.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        count = db.count_last_added_rows("test_table")
        db.drop_table("test_table")

        assert count == 0


def test_count_uniques(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection count_uniques method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF516", ["0xF24", "0xF21"], [100, 13]),
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
                ("0xF518", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        count = db.count_uniques("test_table", "peer_id")
        db.drop_table("test_table")

        assert count == 4


def test_count_uniques_empty(db_fixture: DatabaseConnection, cols_fixture: list[tuple]):
    """
    Test DatabaseConnection count_uniques method with empty table.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        count = db.count_uniques("test_table", "peer_id")
        db.drop_table("test_table")

        assert count == 0


def test_count_uniques_in_last_added_rows(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection count_uniques_in_last_added_rows method.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF516", ["0xF24", "0xF21"], [100, 13]),
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
                ("0xF518", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        count = db.count_uniques_in_last_added_rows("test_table", "peer_id")
        db.drop_table("test_table")

        assert count == 3


def test_count_uniques_in_last_added_rows_empty(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection count_uniques_in_last_added_rows method with empty table.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        count = db.count_uniques_in_last_added_rows("test_table", "peer_id")
        db.drop_table("test_table")

        assert count == 0


def test_rows_after_timestamp_empty(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection rows_after_timestamp method when theres nothing in the db.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        rows = db.rows_after_timestamp("test_table", datetime(1970, 1, 1, 0, 0, 0, 0))
        db.drop_table("test_table")

        assert rows == []


def test_rows_after_timestamp_to_recent(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection rows_after_timestamp method when timestamp is to recent.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF516", ["0xF24", "0xF21"], [100, 13]),
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        rows = db.rows_after_timestamp("test_table", datetime.now())
        db.drop_table("test_table")

        assert rows == []


def test_rows_after_timestamp(
    db_fixture: DatabaseConnection, cols_fixture: list[tuple]
):
    """
    Test DatabaseConnection rows_after_timestamp method when there is content to return.
    """
    with db_fixture as db:
        db.create_table("test_table", cols_fixture)
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF516", ["0xF24", "0xF21"], [100, 13]),
                ("0xF517", ["0xF24", "0xF21"], [100, 13]),
            ],
        )

        time.sleep(5)
        db.insert_many(
            "test_table",
            ["peer_id", "node_addresses", "latency_metric"],
            [
                ("0xF518", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
                ("0xF519", ["0xF24", "0xF21"], [100, 13]),
            ],
        )
        rows = db.rows_after_timestamp(
            "test_table", datetime.now() - timedelta(seconds=4)
        )
        db.drop_table("test_table")

        assert len(rows) == 3


def test_database_name(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection database name.
    """
    with db_fixture as db:
        assert db.database == "metricDB"


def test_database_name_modification(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection database name lock.
    """
    with db_fixture as db:
        with pytest.raises(AttributeError):
            db.database = "random_database"


def test_database_host(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection database host.
    """
    with db_fixture as db:
        assert db.host == "localhost"


def test_database_host_modification(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection database host lock.
    """
    with db_fixture as db:
        with pytest.raises(AttributeError):
            db.host = "random_host"


def test_database_user(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection database user.
    """
    with db_fixture as db:
        assert db.user == "postgres"


def test_database_user_modification(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection database port lock.
    """
    with db_fixture as db:
        with pytest.raises(AttributeError):
            db.user = "random_user"


def test_database_port(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection database port.
    """
    with db_fixture as db:
        assert db.port == "5432"


def test_database_port_modification(db_fixture: DatabaseConnection):
    """
    Test DatabaseConnection database port lock.
    """
    with db_fixture as db:
        with pytest.raises(AttributeError):
            db.port = "random_port"
