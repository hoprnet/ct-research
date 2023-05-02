import asyncio
import requests
import pytest
import json
import logging

from pytest_mock import mocker
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
       

def test_req_returns_valid_json() -> None:
    """
    Test that _req returns a valid json dictionary when the response status code is 200
    and the content type is 'application/json'.
    """
    class Http_req_mock():
        async def send_async_req(self, method: str, target_url: str, headers: dict[str, str], payload: dict[str, str]) -> requests.Response:
            expected_result = {'result': 'success'}
            expected_response = requests.Response()
            expected_response.status_code = 200
            expected_response.headers = {'Content-Type': 'application/json'}
            expected_response._content = json.dumps(expected_result).encode('utf-8')
            return expected_response
    
    class MockHoprNode(HoprNode):
        def __init__(self, url: str, key: str):
            """
            Patched constructor: connected and started
            """
            super().__init__(url, key)
            self.http_req = Http_req_mock()

    async def test_response() -> None:

        node = MockHoprNode("some_url", "some_api_key")
        endpoint = "/some_valid_endpoint"
        expected_url = node._get_url(endpoint)

        expected_result = {'result': 'success'}
        result = await node._req(target_url=expected_url, method="GET")
        assert result == expected_result

    loop = asyncio.new_event_loop()
    print("loop running ...")
    loop.run_until_complete(test_response())
    print("loop closed")
    loop.close()


def test_req_returns_invalid_status_code(caplog) -> None:
    """
    Test that _req method returns the correct log error message when the status code is invalid.
    """
    class Http_req_mock_invalid_status_code():
        async def send_async_req(self, method: str, target_url: str, headers: dict[str, str], payload: dict[str, str]) -> requests.Response:
            expected_response = requests.Response()
            expected_response.status_code = 'SOME_INVALID_STATUS_CODE' 
            return expected_response


    class MockHoprNode(HoprNode):
        def __init__(self, url: str, key: str):
            """
            Patched constructor: connected and started
            """
            super().__init__(url, key)
            self.http_req = Http_req_mock_invalid_status_code()

    async def test_response(caplog) -> dict[str, str]:
            node = MockHoprNode("some_url", "some_api_key")
            endpoint = "/some_valid_endpoint"
            expected_url = node._get_url(endpoint)
            method = "GET"

            with caplog.at_level(logging.ERROR):
                expected_response = await node.http_req.send_async_req(method=method, target_url=expected_url, headers={}, payload={})
                result = await node._req(target_url=expected_url, method=method)

            assert "{} {} returned status code {}".format(method, expected_url, expected_response.status_code) in caplog.text
            return result 

    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_response(caplog))
    loop.close()


def test_req_returns_invalid_content_type(caplog) -> None:
    """
    Test that _req returns a log error with the correct message when the response status code is 200
    but the content type is not 'application/json'.
    """
    class Http_req_mock_invalid_content_type():
        async def send_async_req(self, method: str, target_url: str, headers: dict[str, str], payload: dict[str, str]) -> requests.Response:
            expected_response = requests.Response()
            expected_response.status_code = 200
            expected_response.headers = {'Content-Type': 'SOME_INVALID_CONTENT'}
            return expected_response

    class MockHoprNode(HoprNode):
        def __init__(self, url: str, key: str):
            """
            Patched constructor: connected and started
            """
            super().__init__(url, key)
            self.http_req = Http_req_mock_invalid_content_type()

    async def test_response(caplog) -> dict[str, str]:
            node = MockHoprNode("some_url", "some_api_key")
            endpoint = "/some_valid_endpoint"
            expected_url = node._get_url(endpoint)
            method = "GET"

            with caplog.at_level(logging.ERROR):
                expected_response = await node.http_req.send_async_req(method=method, target_url=expected_url, headers={}, payload={})
                result = await node._req(target_url=expected_url, method=method)

            assert "Expected application/json, but got {}".format(expected_response.headers['Content-Type']) in caplog.text
            # return result to check whether {'response': response.text} gets called correctly
            return result

    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_response(caplog))
    loop.close()


@pytest.fixture
def get_mock_node_for_connect():
    class MockHoprNode(HoprNode):
        def __init__(self, url: str, key: str):
            super().__init__(url, key)

        async def start(self):
            """
            Starts the tasks of this node
            """
            if len(self.tasks) == 0:
                self.started = True
                self.tasks.add(asyncio.create_task(self.connect()))
                await asyncio.gather(*self.tasks)
    return MockHoprNode("some_url", "some_api_key")


@pytest.mark.asyncio 
async def test_connect_successful(mocker, event_loop, caplog, get_mock_node_for_connect):
    """
    Test that the method connects successfully to the HOPR node and sets the correct peer_id
    attribute value.
    """
    def assert_expression():
        assert node.peer_id == json_body["hopr"]

    caplog.set_level(logging.DEBUG)
    node = get_mock_node_for_connect
    json_body = {"hopr": "some_peer_id"}
    mocker.patch.object(node, "_req", return_value=json_body)

    event_loop.call_later(1, lambda: assert_expression())
    event_loop.call_later(2, lambda: node.stop())
    await node.start()


@pytest.mark.asyncio 
async def test_connect_failed_request(mocker, event_loop, get_mock_node_for_connect):
    """
    When the HTTP request fails due to a network error even though the node is started test that peer_id is set to None.
    """
    node = get_mock_node_for_connect
    mocker.patch.object(node, "_req", side_effect=requests.exceptions.ConnectionError())
    
    event_loop.call_later(1, lambda: node.stop())
    await node.start()
    assert node.peer_id is None


@pytest.mark.asyncio 
async def test_connect_exception(mocker, event_loop, get_mock_node_for_connect):
    """
    Test that peer_id is set to None due to a network error other than failed HTTP request.
    """
    node = get_mock_node_for_connect
    mocker.patch.object(node, "_req", side_effect=Exception())

    event_loop.call_later(1, lambda: node.stop())
    await node.start()
    assert node.peer_id is None


@pytest.mark.asyncio 
async def test_connect_exception_logging(mocker, caplog, event_loop, get_mock_node_for_connect):
    """
    Test that the correct log message is logged when an exception occurs during the connect method.
    """
    node = get_mock_node_for_connect
    endpoint = "/account/addresses"
    expected_url = node._get_url(endpoint)
    mocker.patch.object(node, "_req", side_effect=Exception())
    
    event_loop.call_later(1, lambda: node.stop())
    await node.start()
    assert "Could not connect to {}".format(expected_url) in caplog.text


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
                await asyncio.sleep(5)

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

    loop.call_later(2, lambda: node.stop())
    loop.run_until_complete(node.start())
    loop.close()


@pytest.mark.asyncio
async def test_gather_peers_retrieves_peers_from_response(mocker):
    """
    Test whether gather_peers retrieves the correct list of peers from the JSON response returned by the _req() method.
    """
    node = HoprNode("some_url", "some_api_key")
    node.peer_id = "some_peer_id"

    # Mock the _req() method to return a JSON response with two peers
    json_response = {"connected": [{"peerId": "some_other_peer_id_1"},
                                   {"peerId": "some_other_peer_id_2"}]} 
    
    mocker.patch.object(node, "_req", return_value=json_response)

    node.started = True
    task = asyncio.create_task(node.gather_peers())
    await asyncio.sleep(1)

    # avoid infinite while loop by setting node.started = False 
    node.started = False 
    await asyncio.sleep(1)

    assert "some_other_peer_id_1" in node.peers
    assert "some_other_peer_id_2" in node.peers
    await asyncio.gather(task)
    