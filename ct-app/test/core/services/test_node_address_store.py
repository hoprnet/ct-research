from core.services.node_address_store import NodeAddressStore


def test_apply_and_lookup():
    store = NodeAddressStore()
    store.apply("0xa", "1.1.1.1")
    store.apply("0xb", "2.2.2.2")

    assert store.ip_for("0xa") == "1.1.1.1"
    assert store.ip_for("0xb") == "2.2.2.2"
    assert store.ip_for("0xc") is None
    assert len(store) == 2


def test_apply_overwrites_existing_ip():
    store = NodeAddressStore()
    store.apply("0xa", "1.1.1.1")
    store.apply("0xa", "9.9.9.9")

    assert store.ip_for("0xa") == "9.9.9.9"
    assert len(store) == 1


def test_sweep_drops_nodes_absent_from_latest_snapshot():
    store = NodeAddressStore()

    store.start_generation()
    store.apply("kept", "1.1.1.1")
    store.apply("gone", "2.2.2.2")

    store.start_generation()
    store.apply("kept", "1.1.1.1")

    assert store.sweep() == 1
    assert store.ip_for("kept") == "1.1.1.1"
    assert store.ip_for("gone") is None
