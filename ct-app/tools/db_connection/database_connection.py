import datetime
from psycopg2 import connect
from psycopg2.sql import SQL, Identifier
from tools import getlogger

log = getlogger()


class DatabaseConnection:
    def __init__(
        self,
        database: str,
        host: str,
        user: str,
        password: str,
        port: str,
        tablename: str,
    ):
        self._database = database
        self._host = host
        self._user = user
        self._port = port
        self._tablename = tablename

        self.conn = connect(
            database=self._database,
            host=self._host,
            user=self._user,
            password=password,
            port=self._port,
        )
        self.cursor = self.conn.cursor()

        log.info(f"Database connection established as {self._user}")

    @property
    def database(self):
        """Database name getter"""
        return self._database

    @property
    def host(self):
        """Host name getter"""
        return self._host

    @property
    def user(self):
        """User name getter"""
        return self._user

    @property
    def port(self):
        """Port getter"""
        return self._port

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_connection()

    def close_connection(self):
        """
        Closes the database connection.
        """
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

        log.info(f"Database connection closed as {self._user}")

    def create_table(self, columns: list[str] = []):
        """
        Creates a table with the given columns.
        :param columns: A list of tuples containing the column name and the column type.
        :raise: ValueError if the table already exists.
        """
        if self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' already exist")

        table_id = Identifier(self._tablename)

        command = SQL(
            """
            CREATE TABLE {} (
                {}
            );
        """
        )

        # create sql command with columns names and types from columns list
        columns_sql = SQL(", ").join(
            SQL("{} {}").format(Identifier(name), SQL(type_)) for name, type_ in columns
        )

        self.cursor.execute(command.format(table_id, columns_sql))
        self.conn.commit()

        log.info(f"Table `{self._tablename}` created with {len(columns)} columns")

    def drop_table(self):
        """
        Drops a table from the database.
        :raise: ValueError if the table does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        table_id = Identifier(self._tablename)
        command = SQL(
            """
            DROP TABLE {};
        """
        )

        self.cursor.execute(command.format(table_id))
        self.conn.commit()

        log.info(f"Table `{self._tablename}` dropped")

    def table_exists_guard(self):
        """
        Checks if a table exists in the database.
        :raise: ValueError if the table does not exist.
        """
        command = SQL(
            """
            SELECT EXISTS (
                SELECT FROM 
                    information_schema.tables
                WHERE 
                    table_name  = %s
                );
        """
        )
        self.cursor.execute(command, (self._tablename,))
        return self.cursor.fetchone()[0]

    def column_exists_guard(self, column: str):
        """
        Checks if a column exists in a table.
        :param column: The name of the column to check.
        :return: True if the column exists, False otherwise.
        :raise: ValueError if the table does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        command = SQL(
            """
            SELECT EXISTS (
                SELECT FROM 
                    information_schema.columns
                WHERE 
                    table_name  = %s AND column_name = %s
                );
        """
        )
        self.cursor.execute(command, (self._tablename, column))
        return self.cursor.fetchone()[0]

    def non_default_columns(self):
        """
        Gets names for all columns that do not have a default value in the given table.
        :return: A list of column names.
        :raise: ValueError if the table does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        command = SQL(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s AND column_default IS NULL;
        """
        )
        self.cursor.execute(command, (self._tablename,))
        return [row[0] for row in self.cursor.fetchall()]

    def insert(self, **kwargs):
        """
        Inserts a row into the given table.
        :param **kwargs: The column names and values to insert.
        :raise: ValueError if the table does not exist or if a column does not exist.
        :raise: ValueError if a column is missing.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        # check if all columns are in table
        for key in kwargs.keys():
            if not self.column_exists_guard(key):
                raise ValueError(
                    f"Column '{key}' does not exist in table '{self._tablename}'"
                )

        # check that all table's column are in kwargs
        for column in self.non_default_columns():
            if column not in kwargs.keys():
                raise ValueError(f"Column '{column}' is missing")

        table_id = Identifier(self._tablename)
        keys = list(kwargs.keys())
        values = list(kwargs.values())

        # insert data into table with columns names from keys and values from values
        command = SQL(
            """
            INSERT INTO {} ({})
            VALUES ({})
        """
        )

        self.cursor.execute(
            command.format(
                table_id,
                SQL(", ").join(Identifier(key) for key in keys),
                SQL(", ").join(SQL("%s") for _ in values),
            ),
            values,
        )
        self.conn.commit()

        log.info(f"Row inserted into `{self._tablename}`")

    def insert_many(self, keys: list[str], values: list[tuple]):
        """
        Inserts multiple rows into the given table.
        :param keys: A list of column names to insert.
        :param values: A list of tuples containing the column names/values to insert.
        :raise: ValueError if the table does not exist or if a column does not exist.
        :raise: ValueError if a column is missing.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        # check if all columns are in table
        for key in keys:
            if not self.column_exists_guard(key):
                raise ValueError(
                    f"Column '{key}' does not exist in table '{self._tablename}'"
                )

        # check that all table's column are in kwargs
        for column in self.non_default_columns():
            if column not in keys:
                raise ValueError(f"Column '{column}' is missing")

        table_id = Identifier(self._tablename)

        # insert data into table with columns names from keys and values from values
        command = SQL(
            """
            INSERT INTO {} ({})
            VALUES {}
        """
        )

        value_item_joined = []
        for value in values:
            sql_line = SQL("(") + SQL(", ").join(SQL("%s") for _ in value) + SQL(")")
            value_item_joined.append(sql_line)

        value_joined = SQL(", ").join(value_item_joined)
        separated_values = [item for value in values for item in value]

        command_formatted = command.format(
            table_id,
            SQL(", ").join(Identifier(key) for key in keys),
            value_joined,
        )

        self.cursor.execute(
            command_formatted,
            separated_values,
        )
        self.conn.commit()

        log.info(f"{len(values)} rows inserted into `{self._tablename}`")

    def last_row(self):
        """
        Gets the last row from the given table.
        :return: The row as a tuple.
        :raise: ValueError if the table does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        table_id = Identifier(self._tablename)

        command = SQL(
            """
            SELECT *
            FROM {}
            WHERE id = (SELECT MAX(id) FROM {})
        """
        )
        self.cursor.execute(command.format(table_id, table_id))
        result = self.cursor.fetchall()

        if len(result) == 0:
            return None

        log.info(f"Last row fetched from `{self._tablename}`")

        return result[0]

    def row(self, row: int):
        """
        Gets a row from the given table.
        :param row: The row to get.
        :return: The row as a tuple.
        :raise: ValueError if the table does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        table_id = Identifier(self._tablename)

        command = SQL(
            """
            SELECT *
            FROM {}
            WHERE id = (%s)
        """
        )
        self.cursor.execute(command.format(table_id), (row,))
        result = self.cursor.fetchall()

        if len(result) == 0:
            return None

        log.info(f"Row {row} fetched from `{self._tablename}`")

        return result[0]

    def last_added_rows(self):
        """
        Gets the last added rows from the given table based on the timestamp column.
        :return: The rows as a tuple.
        :raise: ValueError if the table does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        table_id = Identifier(self._tablename)

        command = SQL(
            """
            SELECT *
            FROM {}
            WHERE timestamp = (SELECT MAX(timestamp) FROM {})
        """
        )
        self.cursor.execute(command.format(table_id, table_id))
        result = self.cursor.fetchall()

        if len(result) == 0:
            log.warning(
                f"No rows fetched from `{self._tablename}` because no data was found"
            )
            return None

        log.info(f"Last added rows ({len(result)}) fetched from `{self._tablename}`")

        return result

    def count_last_added_rows(self):
        """
        Counts the last added rows from the given table based on the timestamp column.
        :return: The number of rows.
        :raise: ValueError if the table does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        table_id = Identifier(self._tablename)

        command = SQL(
            """
            SELECT COUNT(*)
            FROM {}
            WHERE timestamp = (SELECT MAX(timestamp) FROM {})
        """
        )
        self.cursor.execute(command.format(table_id, table_id))
        count = self.cursor.fetchone()[0]

        log.info(f"Counted last added rows from `{self._tablename}`: {count}")

        return count

    def count_uniques(self, column: str):
        """
        Counts the unique values in the given column of the given table.
        :param column: The name of the column to count the values from.
        :return: The number of unique values.
        :raise: ValueError if the table or the column does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        if not self.column_exists_guard(column):
            raise ValueError(
                f"Column '{column}' does not exist in table '{self._tablename}'"
            )

        table_id = Identifier(self._tablename)
        column_id = Identifier(column)

        command = SQL(
            """
            SELECT COUNT(DISTINCT {})
            FROM {}
        """
        )
        self.cursor.execute(command.format(column_id, table_id))
        count = self.cursor.fetchone()[0]

        log.info(
            f"Counted unique values in column `{column}` of `{self._tablename}`: {count}"
        )

        return count

    def count_uniques_in_last_added_rows(self, column: str):
        """
        Counts the unique values in the given column of the last added rows of the given
        table.
        :param column: The name of the column to count the values from.
        :return: The number of unique values.
        :raise: ValueError if the table or the column does not exist.
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")

        if not self.column_exists_guard(column):
            raise ValueError(
                f"Column '{column}' does not exist in table '{self._tablename}'"
            )

        table_id = Identifier(self._tablename)
        column_id = Identifier(column)

        command = SQL(
            """
            SELECT COUNT(DISTINCT {})
            FROM {}
            WHERE timestamp = (SELECT MAX(timestamp) FROM {})
        """
        )
        self.cursor.execute(command.format(column_id, table_id, table_id))
        count = self.cursor.fetchone()[0]

        log.info(
            f"Counted last unique values in column `{column}` of `{self._tablename}`: {count}"
        )

        return count

    def rows_after_timestamp(self, timestamp: datetime.datetime):
        """
        Gets the rows from the given table that have a timestamp more recent than the given
        timestamp.
        :param timestamp: The timestamp to compare to.
        :return: The rows as a tuple.
        :raise: ValueError if the table does not exist or if the timestamp is not a
        """
        if not self.table_exists_guard():
            raise ValueError(f"Table '{self._tablename}' does not exist")
        if not isinstance(timestamp, datetime.datetime):
            raise ValueError("Timestamp must be a    datetime.datetime object")

        table_id = Identifier(self._tablename)

        command = SQL(
            """
            SELECT *
            FROM {}
            WHERE timestamp > (%s)
        """
        )
        self.cursor.execute(command.format(table_id), (timestamp,))
        result = self.cursor.fetchall()

        log.info(f"Rows after {timestamp} fetched from `{self._tablename}`")

        return result
