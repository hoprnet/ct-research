from enum import Enum

class ExitCode(Enum):
    OK = 0
    ERROR = 1
    ERROR_TIMEOUT = 2
    ERROR_BAD_ARGUMENTS = 3
    ERROR_UNCAUGHT_EXCEPTION = 4
    