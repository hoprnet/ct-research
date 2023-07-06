from unittest.mock import MagicMock
from signal import SIGINT

from economic_handler.economic_handler import EconomicHandler
from economic_handler.utils_econhandler import stop_instance


def test_stop_instance():
    """
    Test whether the stop function correctly calls the stop method of the node object
    with the SIGINT signal.
    """
    node = EconomicHandler("some_url", "some_key", "some_rpch_endpoint")

    # Create a mock object of the stop method of the EconomicHandler class
    # to test whether the stop method calls the mock object.
    node.stop = MagicMock()

    stop_instance(node, SIGINT)

    node.stop.assert_called_once()
