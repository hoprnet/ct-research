from ct.exit_codes import ExitCode
from ct.utils import _getenvvar

from .netwatcher import NetWatcher


def main():
    try:
        API_host = _getenvvar("HOPR_NODE_1_HTTP_URL")
        API_key = _getenvvar("HOPR_NODE_1_API_KEY")
    except ValueError:
        exit(ExitCode.ERROR_BAD_ARGUMENTS)
        
    NetWatcher(API_host, API_key)


if __name__ == "__main__":
    main()