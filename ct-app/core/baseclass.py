class Base:
    @property
    def print_prefix(self) -> str:
        return ""

    def _print(self, message: str, color: str = "\033[0m"):
        print(color, end="")
        print(f"{self.print_prefix} // {message}", end="")
        print("\033[0m")

    def _debug(self, message: str):
        self._print(message, color="\033[0;32m")

    def _info(self, message: str):
        self._print(message, color="\033[0;34m")

    def _warning(self, message: str):
        self._print(message, color="\033[0;33m")

    def _error(self, message: str):
        self._print(message, color="\033[0;31m")
