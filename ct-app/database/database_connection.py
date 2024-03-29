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
        self.params = Parameters()("PG")

        self._assert_parameters()

        url = URL(
            drivername="postgresql+psycopg2",
            username=self.params.pg.user,
            password=self.params.pg.password,
            host=self.params.pg.host,
            port=self.params.pg.port,
            database=self.params.pg.database,
            query={
                "sslmode": self.params.pg.sslmode,
                "sslrootcert": self.params.pg.sslrootcert,
                "sslcert": self.params.pg.sslcert,
                "sslkey": self.params.pg.sslkey,
            },
        )

        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        log.info("Database connection established.")

    def _assert_parameters(self):
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
        return {
            "pg": [
                "user",
                "password",
                "host",
                "port",
                "database",
                "sslmode",
                "sslrootcert",
                "sslcert",
                "sslkey",
            ]
        }

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()
        self.engine.dispose()
        log.info("Database connection closed.")
