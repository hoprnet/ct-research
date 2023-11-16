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

    This class requires the following environment variables to be set:
    - PGUSER: the database user name
    - PGPASSWORD: the database user password
    - PGHOST: the database host
    - PGPORT: the database port
    - PGDATABASE: the database name
    - PGSSLMODE: the SSL mode
    - PGSSLROOTCERT: the SSL root certificate
    - PGSSLCERT: the SSL certificate
    - PGSSLKEY: the SSL key
    """

    def __init__(self):
        self.params = Parameters()(env_prefix="PG")

        url = URL(
            drivername="postgresql+psycopg2",
            username=self.params.user,
            password=self.params.password,
            host=self.params.host,
            port=self.params.port,
            database=self.params.database,
            query={
                "sslmode": self.params.sslmode,
                "sslrootcert": self.params.sslrootcert,
                "sslcert": self.params.sslcert,
                "sslkey": self.params.sslkey,
            },
        )

        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        log.info("Database connection established.")

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()
        self.engine.dispose()
        log.info("Database connection closed.")