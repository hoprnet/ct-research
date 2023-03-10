import asyncio

from hopr_node import HoprNode



def test_url_formatting():
    """
    Test whether the target url is formatted correctly.
    """
    pass


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
