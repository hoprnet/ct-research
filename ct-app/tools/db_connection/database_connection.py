from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session

from tools import getlogger

from .models import Base

log = getlogger()


class DatabaseConnection:
    def __init__(
        self,
        database: str,
        host: str,
        user: str,
        password: str,
        port: str,
    ):
        self._user = user
        url = URL(
            drivername="postgresql",
            username=user,
            password=password,
            host=host,
            port=port,
            database=database,
            query={"sslmode": "disable"},
        )

        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        log.info(f"Database connection established as {self.user}")

    @property
    def user(self):
        """User name getter"""
        return self._user

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()

    def close_connection(self):
        """
        Closes the database connection.
        """
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

        log.info(f"Database connection closed as {self.user}")
