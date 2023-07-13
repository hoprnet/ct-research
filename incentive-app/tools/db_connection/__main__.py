from .database_connection import DatabaseConnection


def main():
    columns = [
        ("id", "SERIAL PRIMARY KEY"),
        ("peer_id", "VARCHAR(255) NOT NULL"),
        ("netw_ids", "VARCHAR(255)[] NOT NULL"),
        ("latency_metric", "INTEGER[] NOT NULL"),
        ("timestamp", "TIMESTAMP NOT NULL DEFAULT NOW()"),
    ]

    with DatabaseConnection(
        database="metricDB",
        host="localhost",
        user="postgres",
        password="admin",
        port="5432",
    ) as db:
        try:
            db.create_table("foo_table", columns=columns)
        except ValueError as e:
            print(e)


if __name__ == "__main__":
    main()
