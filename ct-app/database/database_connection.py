import logging

from core.components.parameters import Parameters
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session

from .models import Base

log = logging.getLogger()


class DatabaseConnection:
    """
    Database connection class.
    """

    def __init__(self, params: Parameters):
        """
        Create a new DatabaseConnection based on environment variables setting user, password, host, port, database, sslmode, sslrootcert, sslcert and sslkey.
        """

        url = URL(
            drivername="postgresql+psycopg2",
            username=params.user,
            password=params.password,
            host=params.host,
            port=params.port,
            database=params.database,
            query={}
        )

        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        log.info("Database connection established.")

    def __enter__(self):
        """
        Return the session (used by context manager)
        """
        return self.session

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Close the session and the engine (used by context manager)
        """
        self.session.close()
        self.engine.dispose()
        log.info("Database connection closed.")
