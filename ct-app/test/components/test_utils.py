import datetime
import os

import pytest
from core.components.utils import Utils
from core.model.address import Address
from core.model.peer import Peer


def test_envvar():
    os.environ["STRING_ENVVAR"] = "string-envvar"
    os.environ["INT_ENVVAR"] = "1"
    os.environ["FLOAT_ENVVAR"] = "1.0"

    assert Utils.envvar("FAKE_STRING_ENVVAR", "default") == "default"
    assert Utils.envvar("STRING_ENVVAR", type=str) == "string-envvar"
    assert Utils.envvar("INT_ENVVAR", type=int) == 1
    assert Utils.envvar("FLOAT_ENVVAR", type=float) == 1.0

    del os.environ["STRING_ENVVAR"]
    del os.environ["INT_ENVVAR"]
    del os.environ["FLOAT_ENVVAR"]


def test_envvarWithPrefix():
    os.environ["TEST_ENVVAR_2"] = "2"
    os.environ["TEST_ENVVAR_1"] = "1"
    os.environ["TEST_ENVVAR_3"] = "3"
    os.environ["TEST_ENVVOR_4"] = "3"

    assert Utils.envvarWithPrefix("TEST_ENVVAR_", type=int) == {
        "TEST_ENVVAR_1": 1,
        "TEST_ENVVAR_2": 2,
        "TEST_ENVVAR_3": 3,
    }

    del os.environ["TEST_ENVVAR_1"]
    del os.environ["TEST_ENVVAR_2"]
    del os.environ["TEST_ENVVAR_3"]
    del os.environ["TEST_ENVVOR_4"]


def test_nodeAddresses():
    os.environ["NODE_ADDRESS_1"] = "address_1"
    os.environ["NODE_ADDRESS_2"] = "address_2"
    os.environ["NODE_KEY_1"] = "address_1_key"
    os.environ["NODE_KEY_2"] = "address_2_key"

    addresses, keys = Utils.nodesAddresses("NODE_ADDRESS_", "NODE_KEY_")
    assert addresses == ["address_1", "address_2"]
    assert keys == ["address_1_key", "address_2_key"]

    del os.environ["NODE_ADDRESS_1"]
    del os.environ["NODE_ADDRESS_2"]
    del os.environ["NODE_KEY_1"]
    del os.environ["NODE_KEY_2"]


def test_httpPOST():
    pytest.skip("Not implemented")


def test_mergeTopologyPeersSubgraph():
    pytest.skip("Not implemented")


def test_allowManyNodePerSafe():
    peer_1 = Peer("id_1", "address_1", "v1.0.0")
    peer_2 = Peer("id_2", "address_2", "v1.1.0")
    peer_3 = Peer("id_3", "address_3", "v1.0.2")
    peer_4 = Peer("id_4", "address_4", "v1.0.0")

    peer_1.safe_address = "safe_address_1"
    peer_2.safe_address = "safe_address_2"
    peer_3.safe_address = "safe_address_3"
    peer_4.safe_address = "safe_address_2"

    source_data = [peer_1, peer_2, peer_3, peer_4]

    assert all([peer.safe_address_count == 1 for peer in source_data])

    Utils.allowManyNodePerSafe(source_data)

    assert peer_1.safe_address_count == 1
    assert peer_2.safe_address_count == 2
    assert peer_3.safe_address_count == 1


def test_excludeElements():
    source_data = [
        Peer("id_1", "address_1", "v1.0.0"),
        Peer("id_2", "address_2", "v1.1.0"),
        Peer("id_3", "address_3", "v1.0.2"),
        Peer("id_4", "address_4", "v1.0.0"),
        Peer("id_5", "address_5", "v1.1.1"),
    ]
    blacklist = [Address("id_2", "address_2"), Address("id_4", "address_4")]

    excluded = Utils.exclude(source_data, blacklist)

    assert len(source_data) == 3
    assert len(excluded) == 2
    for item in excluded:
        assert item.address in blacklist


def test_rewardProbability():
    pass


def test_jsonFromGCP():
    pytest.skip("Not implemented")


def test_stringArrayToGCP():
    pytest.skip("Not implemented")


def test_generateFilename():
    prefix = "file_prefix"
    folder = "folder"
    ext = "ext"
    filename = Utils.generateFilename(prefix, folder, ext)

    assert filename.startswith(folder)
    assert filename.index(folder) < filename.index(prefix) < filename.index(ext)


def test_nextEpoch():
    timestamp = Utils.nextEpoch(1000)
    now = datetime.datetime.now()

    assert now < timestamp
    assert (timestamp - now).total_seconds() < 1000


def test_nextDelayInSeconds():
    delay = Utils.nextDelayInSeconds(1000)
    assert delay < 1000

    delay = Utils.nextDelayInSeconds(0)
    assert delay == 1

    delay = Utils.nextDelayInSeconds(1)
    assert delay == 1


def test_aggregatePeerBalanceInChannels():
    pytest.skip("Not implemented")


def test_taskSendMessage():
    pytest.skip("Not implemented")


def test_taskStoreFeedback():
    pytest.skip("Not implemented")
