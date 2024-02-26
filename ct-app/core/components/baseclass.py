import logging

logging.basicConfig()
logging.getLogger("asyncio").setLevel(logging.WARNING)
formatter = logging.Formatter("%(levelname)s:%(message)s")


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

    def print_prefix(self) -> str:
        cls = self.__class__
        raise NotImplementedError(
            f"print_prefix not implemented for class '{cls.__name__}'"
        )

    @classmethod
    def class_prefix(cls) -> str:
        return f"{cls.__name__.upper()}_"

    def __format(self, message: str, color: str = "\033[0m"):
        return f"{self.print_prefix()} {message}"

    def callback(self, type: str):
        return getattr(self.logger, type)

    def debug(self, message: str, color: str = "\033[0;32m"):
        self.callback("debug")(self.__format(message, color))

    def info(self, message: str, color: str = "\033[0;34m"):
        self.callback("info")(self.__format(message, color))

    def warning(self, message: str, color: str = "\033[0;33m"):
        self.callback("warning")(self.__format(message, color))

    def error(self, message: str, color: str = "\033[0;31m"):
        self.callback("error")(self.__format(message, color))

    def feature(self, message: str, color: str = "\033[0;35m"):
        self.callback("warning")(self.__format(message, color))
