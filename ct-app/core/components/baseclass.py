import logging

logging.basicConfig()
logging.getLogger("asyncio").setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s %(levelname)s:%(message)s")


class Base:
    """
    Base class for logging and printing messages with different colors.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger("ct-app")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    @property
    def print_prefix(self) -> str:
        return ""

    @classmethod
    def class_prefix(cls) -> str:
        return cls.__name__.lower()

    def __format(self, message: str):
        return f"{self.print_prefix} | {message}"

    def debug(self, message: str):
        self.logger.debug(self.__format(message))

    def info(self, message: str):
        self.logger.info(self.__format(message))

    def warning(self, message: str):
        self.logger.warning(self.__format(message))

    def error(self, message: str):
        self.logger.error(self.__format(message))

    def feature(self, message: str):
        self.logger.info(self.__format(message))
