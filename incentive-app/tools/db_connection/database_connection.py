from psycopg2 import connect
from psycopg2.sql import SQL, Identifier
from psycopg2.errors import NotNullViolation, InFailedSqlTransaction


class DatabaseConnection:
    def __init__(self, database: str, host: str, user: str, password: str, port: str):
        self._database = database
        self._host = host
        self._user = user
        self._port = port

        self.conn = connect(
            database=self._database,
            host=self._host,
            user=self._user,
            password=password,
            port=self._port,
        )
        self.cursor = self.conn.cursor()

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
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

    def create_table(self, table: str, columns: list[str] = []):
        """
        Creates a table with the given columns.
        :param table: The name of the table to create.
        :param columns: A list of tuples containing the column name and the column type.
        """

        if self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' already exist")

        table_id = Identifier(table)

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

    def drop_table(self, table: str):
        """
        Drops a table from the database.
        :param table: The name of the table to drop.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        table_id = Identifier(table)
        command = SQL(
            """
            DROP TABLE {};
        """
        )

        self.cursor.execute(command.format(table_id))
        self.conn.commit()

    def table_exists_guard(self, table: str):
        """
        Checks if a table exists in the database.
        :param table: The name of the table to check.
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
        self.cursor.execute(command, (table,))
        return self.cursor.fetchone()[0]

    def column_exists_guard(self, table: str, column: str):
        """
        Checks if a column exists in a table.
        :param table: The name of the table to check.
        :param column: The name of the column to check.
        :return: True if the column exists, False otherwise.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

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
        self.cursor.execute(command, (table, column))
        return self.cursor.fetchone()[0]

    def non_default_columns(self, table: str):
        """
        Gets names for all columns that do not have a default value in the given table.
        :param table: The name of the table to get columns from.
        :return: A list of column names.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        command = SQL(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s AND column_default IS NULL;
        """
        )
        self.cursor.execute(command, (table,))
        return [row[0] for row in self.cursor.fetchall()]

    def insert(self, table: str, **kwargs):
        """
        Inserts a row into the given table.
        :param table: The name of the table to insert into.
        :param **kwargs: The column names and values to insert.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        # check if all columns are in table
        for key in kwargs.keys():
            print(key)
            if not self.column_exists_guard(table, key):
                print("MISSING KEY")
                raise ValueError(f"Column '{key}' does not exist in table '{table}'")

        # check that all table's column are in kwargs
        for column in self.non_default_columns(table):
            if column not in kwargs.keys():
                raise ValueError(f"Column '{column}' is missing")

        table_id = Identifier(table)
        keys = list(kwargs.keys())
        values = list(kwargs.values())

        # insert data into table with columns names from keys and values from values
        command = SQL(
            """
            INSERT INTO {} ({})
            VALUES ({})
        """
        )

        try:
            self.cursor.execute(
                command.format(
                    table_id,
                    SQL(", ").join(Identifier(key) for key in keys),
                    SQL(", ").join(SQL("%s") for _ in values),
                ),
                values,
            )
        except NotNullViolation as e:
            raise ValueError(e)
        except InFailedSqlTransaction as e:
            raise ValueError(e)
        else:
            self.conn.commit()

    def insert_many(self, table: str, keys: list[str], values: list[tuple]):
        """
        Inserts multiple rows into the given table.
        :param table: The name of the table to insert into.
        :param keys: A list of column names to insert.
        :param values: A list of tuples containing the column names/values to insert.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        # check if all columns are in table
        for key in keys:
            if not self.column_exists_guard(table, key):
                raise ValueError(f"Column '{key}' does not exist in table '{table}'")

        # check that all table's column are in kwargs
        for column in self.non_default_columns(table):
            if column not in keys:
                raise ValueError(f"Column '{column}' is missing")

        table_id = Identifier(table)

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

        try:
            self.cursor.execute(
                command_formatted,
                separated_values,
            )
        except NotNullViolation as e:
            raise ValueError(e)
        else:
            self.conn.commit()

    def last_row(self, table: str):
        """
        Gets the last row from the given table.
        :param table: The name of the table to get the row from.
        :return: The row as a tuple.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        table_id = Identifier(table)

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

        return result[0]

    def row(self, table: str, row: int):
        """
        Gets a row from the given table.
        :param table: The name of the table to get the row from.
        :param row: The row to get.
        :return: The row as a tuple.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        table_id = Identifier(table)

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

        return result[0]

    def last_added_rows(self, table: str):
        """
        Gets the last added rows from the given table based on the timestamp column.
        :param table: The name of the table to get the rows from.
        :return: The rows as a tuple.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        table_id = Identifier(table)

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
            return None

        return result

    def count_last_added_rows(self, table: str):
        """
        Counts the last added rows from the given table based on the timestamp column.
        :param table: The name of the table to count the rows from.
        :return: The number of rows.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        table_id = Identifier(table)

        command = SQL(
            """
            SELECT COUNT(*)
            FROM {}
            WHERE timestamp = (SELECT MAX(timestamp) FROM {})
        """
        )
        self.cursor.execute(command.format(table_id, table_id))
        return self.cursor.fetchone()[0]

    def count_uniques(self, table: str, column: str):
        """
        Counts the unique values in the given column of the given table.
        :param table: The name of the table to count the values from.
        :param column: The name of the column to count the values from.
        :return: The number of unique values.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        if not self.column_exists_guard(table, column):
            raise ValueError(f"Column '{column}' does not exist in table '{table}'")

        table_id = Identifier(table)
        column_id = Identifier(column)

        command = SQL(
            """
            SELECT COUNT(DISTINCT {})
            FROM {}
        """
        )
        self.cursor.execute(command.format(column_id, table_id))
        return self.cursor.fetchone()[0]

    def count_uniques_in_last_added_rows(self, table: str, column: str):
        """
        Counts the unique values in the given column of the last added rows of the given
        table.
        :param table: The name of the table to count the values from.
        :param column: The name of the column to count the values from.
        :return: The number of unique values.
        """
        if not self.table_exists_guard(table):
            raise ValueError(f"Table '{table}' does not exist")

        if not self.column_exists_guard(table, column):
            raise ValueError(f"Column '{column}' does not exist in table '{table}'")

        table_id = Identifier(table)
        column_id = Identifier(column)

        command = SQL(
            """
            SELECT COUNT(DISTINCT {})
            FROM {}
            WHERE timestamp = (SELECT MAX(timestamp) FROM {})
        """
        )
        self.cursor.execute(command.format(column_id, table_id, table_id))
        return self.cursor.fetchone()[0]
