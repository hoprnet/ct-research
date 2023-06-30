# import pytest
# import os
# from unittest.mock import MagicMock
# from signal import SIGINT

# from tools import HOPRNode, _getenvvar, stop


# def test_getenvvar_load_envar() -> None:
#     """
#     Test whether the global environment variables are loaded correctly.
#     """
#     os.environ["HOPR_NODE_1_HTTP_URL"] = "http_url"
#     os.environ["HOPR_NODE_1_API_KEY"] = "api_key"

#     envvar_0 = _getenvvar("HOPR_NODE_1_HTTP_URL")
#     envvar_1 = _getenvvar("HOPR_NODE_1_API_KEY")

#     assert envvar_0 == "http_url"
#     assert envvar_1 == "api_key"


# def test_getenvvar_exit() -> None:
#     """
#     Test whether system exit is called when no environemnt variable is provided.
#     """

#     with pytest.raises(ValueError):
#         _getenvvar("NO_SUCH_ENV_VAR_EXISTS")


# def test_stop():
#     """
#     Test whether the stop function correctly calls the stop method of the node object
#     with the SIGINT signal.
#     """
#     node = HOPRNode("some_url", "some_key")

#     # Create a mock object of the stop method of the HOPRNode class to test whether the
#     # stop method calls the mock object.
#     node.stop = MagicMock()

#     stop(node, SIGINT)

#     node.stop.assert_called_once()
