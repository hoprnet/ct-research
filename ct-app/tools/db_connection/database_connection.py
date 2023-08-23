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

        log.info(f"Database connection established as `{self.user}`")

    @property
    def user(self):
        """User name getter"""
        return envvar("PGUSER")

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
