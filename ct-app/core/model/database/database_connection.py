import logging

from core.components.parameters import Parameters
from core.components.singleton import Singleton
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session

from .models import Base

log = logging.getLogger()


class DatabaseConnection(metaclass=Singleton):
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
            query={},
        )

        self.engine = create_engine(url, pool_size=5)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        log.info("Database connection established.")

    @classmethod
    def open(cls, params: Parameters):
        return cls(params)

    @classmethod
    def close(cls):
        try:
            instance = cls()
        except Exception as e:
            raise Exception(
                f"Unable to find a running instance of DatabaseConnection: {e}"
            )

        instance.session.close()
        instance.engine.dispose()

    @classmethod
    def session(cls) -> Session:
        try:
            instance = cls()
        except Exception as e:
            raise Exception(
                f"Unable to find a running instance of DatabaseConnection: {e}"
            )
        else:
            return instance.session
