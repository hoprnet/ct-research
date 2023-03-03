import pytest

from hopr_node import HoprNode

key = 'something'
url = "some_url"
end_point = "/account/addresses"

def test_req():
    node = HoprNode(url, key)  # Create an instance of the HoprNode class
    request = node._req(end_point=end_point, method='GET', payload=None) 
    assert request.target_url == "{}/api/v2{}".format(url, end_point)


class MockHoprNode(HoprNode):
    def __init__(self, url: str, key: str):
        """
        Patched constructor: always started
        """
        super().__init__(url, key)
        self.started = True

    def _req(*args, **kwargs) -> dict[str, str]:
        """
        Patch HoprNode._req to return a valid JSON object.
        """
        return {'a': 'b'}


def test_adding_peers_while_pinging() -> None:
    """
    Changing the 'peers' set while pinging should not break.
    """
    node = MockHoprNode("some_host", "some_key")
