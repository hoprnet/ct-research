import asyncio

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
