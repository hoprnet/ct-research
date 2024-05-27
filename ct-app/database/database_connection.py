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

    def __init__(self):
        """
        Create a new DatabaseConnection based on environment variables setting user, password, host, port, database, sslmode, sslrootcert, sslcert and sslkey.
        """
        self.params = Parameters()("PG")
        self._assert_parameters()

        url = URL(
            drivername="postgresql+psycopg2",
            username=self.params.pg.user,
            password=self.params.pg.password,
            host=self.params.pg.host,
            port=self.params.pg.port,
            database=self.params.pg.database,
            query={}
        )

        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        log.info("Database connection established.")

    def _assert_parameters(self):
        """
        Asserts that all required parameters are set.
        """
        for group, values in self.required_parameters().items():
            assert len(getattr(self.params, group).__dict__), (
                f"Missing all '{group.upper()}' environment variables. "
                + "The following ones are required: "
                + f"{', '.join([(group+'(_)'+v).upper() for v in values])}"
            )

            for value in values:
                assert hasattr(self.params.pg, value), (
                    "Environment variable "
                    + f"'{group.upper()}(_){value.upper()}' missing"
                )

    @classmethod
    def required_parameters(cls):
        """
        Returns the required parameters for the DatabaseConnection.
        """
        return {
            "pg": [
                "user",
                "password",
                "host",
                "port",
                "database"
            ]
        }

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
