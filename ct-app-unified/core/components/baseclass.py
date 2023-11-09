import logging

logging.basicConfig()
logging.getLogger("asyncio").setLevel(logging.WARNING)
formatter = logging.Formatter("%(message)s")


class Base:
    doLogging = True

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger("ct-app")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    @property
    def print_prefix(self) -> str:
        return ""

    def __format(self, message: str, color: str = "\033[0m"):
        return f"{color}{self.print_prefix}\033[0m | {message}"

    def _print(self, message: str, color: str = "\033[0m"):
        print(self.__format(message, color))

    def _debug(self, message: str):
        color = "\033[0;32m"
        if self.doLogging:
            self.logger.debug(self.__format(message, color))
        else:
            self._print(message, color)

    def _info(self, message: str):
        color = "\033[0;34m"
        if self.doLogging:
            self.logger.info(self.__format(message, color))
        else:
            self._print(message, color)

    def _warning(self, message: str):
        color = "\033[0;33m"

        if self.doLogging:
            self.logger.warning(self.__format(message, color))
        else:
            self._print(message, color)

    def _error(self, message: str):
        color = "\033[0;31m"
        if self.doLogging:
            self.logger.error(self.__format(message, color))
        else:
            self._print(message, color)

    def _feature(self, message: str):
        color = "\033[0;35m"
        if self.doLogging:
            self.logger.info(self.__format(message, color))
        else:
            self._print(message, color)
