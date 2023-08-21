from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session

from tools import envvar, getlogger

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
            query={"sslmode": envvar("PGSSLMODE")},
        )

        # ssl_context = ssl.SSLContext()
        # ssl_context.verify_mode = ssl.CERT_REQUIRED
        # ssl_context.check_hostname = True
        # ssl_context.load_verify_locations(envvar("PGSSLROOTCERT"))
        # ssl_context.load_cert_chain(envvar("PGSSLCERT"), envvar("PGSSLKEY"))

        sql_args = {
            "sslrootcert": envvar("PGSSLROOTCERT"),
            "sslcert": envvar("PGSSLCERT"),
            "sslkey": envvar("PGSSLKEY"),
        }

        self.engine = create_engine(url, connect_args=sql_args, echo=True)

        log.info("AFTER ENGINE")

        Base.metadata.create_all(self.engine)

        log.info("AFTER CREATE ALL")

        self.session = Session(self.engine)

        log.info("AFTER SESSION")

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
