from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session

from tools import envvar, getlogger

from .models import Base

log = getlogger()


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
        url = URL(
            drivername="postgresql+psycopg2",
            username=envvar("PGUSER"),
            password=envvar("PGPASSWORD"),
            host=envvar("PGHOST"),
            port=envvar("PGPORT", int),
            database=envvar("PGDATABASE"),
            query={
                "sslmode": envvar("PGSSLMODE"),
                "sslrootcert": envvar("PGSSLROOTCERT"),
                "sslcert": envvar("PGSSLCERT"),
                "sslkey": envvar("PGSSLKEY"),
            },
        )

        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        # get connected user from session
        self.session.execute("SELECT current_user;")

        log.info("Database connection established.")

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()
        self.engine.dispose()
        log.info("Database connection closed.")
