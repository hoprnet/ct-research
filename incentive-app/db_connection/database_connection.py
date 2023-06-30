from psycopg2 import connect
from psycopg2.sql import SQL, Identifier

class DatabaseConnection:
    def __init__(self, database: str, host: str, user: str, password: str, port: str):
        self._database = database
        self._host = host
        self._user = user
        self._password = password
        self._port = port

        self.conn = connect(database=self._database,
                                host=self._host,
                                user=self._user,
                                password=self._password,
                                port=self._port)
        self.cursor = self.conn.cursor()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

    def insert(self, table:str, peer:str, nws:list[str], latencies:list[int]):
        command = SQL("""
            INSERT INTO {} (peer_id, netw_ids, latency_metric) 
            VALUES (%s, %s, %s)
        """)

        self.cursor.execute(command.format(Identifier(table)), (peer, nws, latencies))
        self.conn.commit()

    def get_row(self, table:str, id:int):
        table_id = Identifier(table)

        if id == -1:
            command = SQL("""
                SELECT peer_id, netw_ids, latency_metric
                FROM {}
                WHERE id = (SELECT MAX(id) FROM {})
            """)
            self.cursor.execute(command.format(table_id, table_id))
        else:
            command = SQL("""
                SELECT peer_id, netw_ids, latency_metric
                FROM {}
                WHERE id = (%s)
            """)
            self.cursor.execute(command.format(table_id), (id,))

        return self.cursor.fetchall()[0]

