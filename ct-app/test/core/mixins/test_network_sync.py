from core.mixins.network_sync import NetworkSyncMixin


class DummyNetworkSyncNode(NetworkSyncMixin):
    pass


def test_on_link_update_requests_network_update_refresh(mocker):
    node = DummyNetworkSyncNode()
    node.network_update_coordinator = mocker.Mock()
    node.channel_lifecycle_coordinator = mocker.Mock()
    network_request_mock = mocker.patch.object(node.network_update_coordinator, "request")
    lifecycle_request_mock = mocker.patch.object(node.channel_lifecycle_coordinator, "request")

    node._on_link_update()

    network_request_mock.assert_called_once_with("account_link_subscription")
    lifecycle_request_mock.assert_called_once_with("account_link_subscription")
