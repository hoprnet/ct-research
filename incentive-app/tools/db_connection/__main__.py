from .database_connection import DatabaseConnection

def main():
    with DatabaseConnection(database="metricDB",
                        host="localhost",
                        user="postgres",
                        password="admin",
                        port="5432") as db:

        db.insert("raw_data_table", "0xF514", ["0xF24", "0xF21"], [100,13])
        peer_id, nws, latencies = db.get_row("raw_data_table", -1)
        print(f"{peer_id=} {nws=} {latencies=}")

if __name__ == "__main__":
    main()