import asyncio
import requests
import pytest
from unittest.mock import patch

import http_req 
from hopr_node import HoprNode


def test_url_formatting():
    """
    Test whether the target url is formatted correctly.
    """
    base_url = "some_url"
    node = HoprNode(base_url, "some_api_key")
    endpoint = "/some_valid_endpoint"
    expected_url = f"{base_url}/api/v2{endpoint}"
    assert node._get_url(endpoint) == expected_url

@pytest.fixture
def patched_http_req(monkeypatch):
    async def patched_send_async_req(method: str, url: str, headers: dict[str, str], payload: dict[str, str]) -> requests.Response:
        print("Patched send_async_req called with URL:", url) # Verify whether the patch gets used 
        expected_result = {'result': 'success'}
        expected_response = requests.Response()
        expected_response.status_code = 200
        expected_response.headers = {'Content-Type': 'application/json'}
        expected_response.json = expected_result
        return expected_response
    monkeypatch.setattr(http_req, "send_async_req", patched_send_async_req)


def test_req_returns_valid_json(patched_http_req: pytest.fixture) -> None:
    """
    Test that _req returns a valid json dictionary when the response status code is 200
    and the content type is 'application/json'.
    """
    async def test_response() -> None:

        node = HoprNode("some_url", "some_api_key")
        endpoint = "/some_valid_endpoint"
        expected_url = node._get_url(endpoint)


        expected_result = {'result': 'success'}
        with patch.object(http_req, 'send_async_req', new=patched_http_req):
            result = await node._req(target_url=expected_url, method="GET")
        assert result == expected_result

    loop = asyncio.new_event_loop()
    print("loop running ...")
    loop.run_until_complete(test_response())
    loop.close()
    print("loop closed")


def test_connected_property():
    """
    Test that the connected property returns false bz default. 
    Test that the connected property returns true after setting a peer_id. 
    """
    node = HoprNode("some_url", "some_api_key")
    assert not node.connected  

    node.peer_id = "some_peer_id"
    assert node.connected  

def test_disconnect_method():
    """
    Test that the node is disconnected after calling disconnect method
    Test that the peer_id attribute is set to None after calling disconnect method 
    """
    node = HoprNode("some_url", "some_api_key")
    node.peer_id = "some_peer_id"
    node.disconnect()
    assert not node.connected 
    assert node.peer_id is None  


def test_adding_peers_while_pinging() -> None:
    """
    Changing the 'peers' set while pinging should not break.
    """
    class MockHoprNode(HoprNode):
        def __init__(self, url: str, key: str):
            """
            Patched constructor: connected and started
            """
            super().__init__(url, key)
            self.started = True

        def _req(*args, **kwargs) -> dict[str, str]:
            """
            Patch HoprNode._req to return a valid JSON object.
            """
            return {'a': 'b'}

        async def connect(self):
            self.peer_id = "testing_peer_id"
            while self.started:
                await asyncio.sleep(45)

        async def gather_peers(self):
            """
            Patched to discover one additional peer every couple of seconds
            """
            while self.started:
                await asyncio.sleep(1)
                peer = 'peer_{}'.format(len(self.peers))
                self.peers.add(peer)

    node = MockHoprNode("some_url", "some_key")
    loop = asyncio.new_event_loop()

    loop.call_later(10, lambda: node.stop())
    loop.run_until_complete(node.start())
    loop.close()
