import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from hopr_node import HoprNode


@pytest.mark.asyncio
async def test_req_invalid_url():
    """
    Test whether a request using _req fails due to an invalid url format.
    """
    node = HoprNode("some_url", "some_key")
    end_point = "/some_valid_endpoint"
    target_url = "{}/api/v2{}".format(node.url, end_point)
    invalid_target_url = "{}/api/v3{}".format(node.url, end_point)
    payload = {"param1": "value1", "param2": "value2"}

    # Define mock response
    mock_response = {
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "response": {"response": "Hello, world!"}
    }

    # Monkeypatch _req method
    with patch.object(node, '_req', new_callable=AsyncMock) as mock_req:
        
        # Test valid URL
        mock_req.return_value = mock_response
        result = await node._req(target_url, "GET", payload)
        assert result["response"]["response"] == "Hello, world!"
        
        # Test invalid URL 
        mock_response["status_code"] = 404
        mock_req.return_value = mock_response
        with pytest.raises(ValueError) as exc_info:
            result = await node._req(invalid_target_url, "GET", payload)
        assert exc_info.type == ValueError

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
