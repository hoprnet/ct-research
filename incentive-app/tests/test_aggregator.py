from sanic.app import Sanic
from aggregator import Aggregator
import pytest
from aggregator.middlewares import attach_middlewares
from aggregator.routes import attach_endpoints

agg = Aggregator()


def clear_instance(func):
    """
    Decorator that clears the instance of the aggregator. This is necessary due
    to the singleton implementation.
    """

    def wrapper(*args, **kwargs):
        agg = Aggregator()
        agg._nw_peer_latency = {}
        agg._nw_last_update = {}

        func(*args, **kwargs)

    return wrapper


@clear_instance
def test_singleton():
    """
    Test that the aggregator is implemented as a singleton.
    """
    agg1 = Aggregator()
    agg2 = Aggregator()

    assert agg1 is agg2


@clear_instance
def test_singleton_update():
    """
    Test that when an instance of the aggregator is updated, all the other instances
    are updated as well.
    """
    agg1 = Aggregator()
    agg2 = Aggregator()

    agg1.add_nw_peer_latencies("pod_id", {"peer": 1})
    agg2.set_nw_update("pod_id", "timestamp")

    assert agg1.get_nw_peer_latencies() == agg2.get_nw_peer_latencies()


@clear_instance
def test_add():
    """
    Test that the add method works correctly.
    """
    pod_id = "pod_id"
    items = {"peer": 1}

    agg.add_nw_peer_latencies(pod_id, items)

    assert agg._nw_peer_latency.get(pod_id) == items


@clear_instance
def test_get():
    """
    Test that the get method works correctly.
    """
    pod_id = "pod_id"
    items = {"peer": 1}

    agg._nw_peer_latency[pod_id] = items

    assert agg.get_nw_peer_latencies() == {pod_id: items}


@clear_instance
def test_clear():
    """
    Test that the clear method works correctly.
    """
    pod_id = "pod_id"
    items = {"peer": 1}

    agg.add_nw_peer_latencies(pod_id, items)

    agg.clear_nw_peer_latencies()

    assert agg._nw_peer_latency == {}


@clear_instance
def test_set_update():
    """
    Test that the set_update method works correctly.
    """
    pod_id = "pod_id"
    timestamp = "timestamp"

    agg.set_nw_update(pod_id, timestamp)

    assert agg._nw_last_update.get(pod_id) == timestamp


@clear_instance
def test_get_update():
    """
    Test that the get_update method works correctly.
    """
    pod_id = "pod_id"
    timestamp = "timestamp"

    agg._nw_last_update[pod_id] = timestamp

    assert agg.get_nw_update(pod_id) == timestamp


@clear_instance
def test_get_update_not_in_dict():
    """
    Test that the get_update method works correctly when the pod_id is not in the dict.
    """
    pod_id = "pod_id"

    assert not agg.get_nw_update(pod_id)


@clear_instance
def test_get_metric():
    """
    Test that the get_metric method works correctly.
    """
    assert isinstance(agg.get_metrics(), dict)


@clear_instance
def test_convert_to_db_data_simple():
    """
    Test that the convert_to_db_data method works correctly.
    """
    pod_id = "pod_id"
    items = {"peer": 1}

    agg.add_nw_peer_latencies(pod_id, items)

    assert agg.convert_to_db_data() == [("peer", ["pod_id"], [1])]


@clear_instance
def test_convert_to_db_data_multiple_peers():
    """
    Test that the convert_to_db_data method works correctly when there are multiple
    items.
    """
    pod_id = "pod_id"
    items = {"peer": 1, "peer2": 2}

    agg.add_nw_peer_latencies(pod_id, items)

    assert agg.convert_to_db_data() == [
        ("peer", ["pod_id"], [1]),
        ("peer2", ["pod_id"], [2]),
    ]


@clear_instance
def test_convert_to_db_data_multiple_pods():
    """
    Test that the convert_to_db_data method works correctly when there are multiple
    pods.
    """
    pod_id = "pod_id"
    pod_id2 = "pod_id2"
    items = {"peer": 1}
    items2 = {"peer2": 2}

    agg.add_nw_peer_latencies(pod_id, items)
    agg.add_nw_peer_latencies(pod_id2, items2)

    assert agg.convert_to_db_data() == [
        ("peer", ["pod_id"], [1]),
        ("peer2", ["pod_id2"], [2]),
    ]


@clear_instance
def test_add_multiple():
    """
    Test that the add method works correctly when adding multiple items.
    """
    pod_id = "pod_id"
    items = {"peer": 1, "peer2": 2}

    agg.add_nw_peer_latencies(pod_id, items)

    assert agg.get_nw_peer_latencies()[pod_id] == items


@clear_instance
def test_add_multiple_pods():
    """
    Test that the add method works correctly when adding multiple pods.
    """
    pod_id = "pod_id"
    pod_id2 = "pod_id2"
    items = {"peer": 1}
    items2 = {"peer2": 2}

    agg.add_nw_peer_latencies(pod_id, items)
    agg.add_nw_peer_latencies(pod_id2, items2)

    assert agg.get_nw_peer_latencies()[pod_id] == items
    assert agg.get_nw_peer_latencies()[pod_id2] == items2


@clear_instance
def test_add_to_existing_pod():
    """
    Test that the add method works correctly when adding to an existing pod.
    """
    pod_id = "pod_id"
    items = {"peer": 1}
    items2 = {"peer2": 2}

    agg.add_nw_peer_latencies(pod_id, items)
    agg.add_nw_peer_latencies(pod_id, items2)

    assert agg.get_nw_peer_latencies()[pod_id] == {"peer": 1, "peer2": 2}


@clear_instance
def test_add_to_existing_pod_multiple():
    """
    Test that the add method works correctly when adding multiple items to an existing
    pod.
    """
    pod_id = "pod_id"
    items = {"peer": 1}
    items2 = {"peer": 2, "peer2": 1}
    items3 = {"peer2": 2}

    agg.add_nw_peer_latencies(pod_id, items)
    agg.add_nw_peer_latencies(pod_id, items2)
    agg.add_nw_peer_latencies(pod_id, items3)

    assert agg.get_nw_peer_latencies()[pod_id] == {"peer": 2, "peer2": 2}


@pytest.fixture
def app():
    """
    This fixture returns a Sanic app.
    """
    app_instance = Sanic("Aggregator")
    attach_endpoints(app_instance)
    attach_middlewares(app_instance)

    app_instance.prepare(dev=True, access_log=False)

    yield app_instance


@pytest.fixture
def test_cli(app):
    """
    This fixture returns a test client.
    """
    return app.test_client


def test_sanic_get_metrics(test_cli):
    """
    This test checks that the get metrics endpoint returns the correct data.
    """
    _, response = test_cli.get("/aggregator/metrics")

    assert response.status == 200
    assert isinstance(response.json, dict)


def test_sanic_post_list_missing_id(test_cli):
    """
    This test checks that the post_list endpoint returns the correct data when
    the id is missing.
    """
    _, response = test_cli.post("/aggregator/list", json={"list": []})

    assert response.status == 400
    assert response.json["message"] == "`id` key not in body"


def test_sanic_post_list_wrong_id_type(test_cli):
    """
    This test checks that the post_list endpoint returns the correct data when
    the value passed as id is not a string
    """
    _, response = test_cli.post(
        "/aggregator/list", json={"id": 123, "list": {"peer": 1}}
    )

    assert response.status == 400
    assert response.json["message"] == "`id` must be a string"


def test_sanic_post_list_missing_list(test_cli):
    """
    This test checks that the post_list endpoint returns the correct data when
    the list is missing.
    """
    _, response = test_cli.post("/aggregator/list", json={"id": "some_id"})

    assert response.status == 400
    assert response.json["message"] == "`list` key not in body"


def test_sanic_post_list_wrong_list_type(test_cli):
    """
    This test checks that the post_list endpoint returns the correct data when
    the value passed as list is not a dict
    """
    _, response = test_cli.post("/aggregator/list", json={"id": "some_id", "list": 123})

    assert response.status == 400
    assert response.json["message"] == "`list` must be a dict"


def test_sanic_post_list_empty_list(test_cli):
    """
    This test checks that the post_list endpoint returns the correct data when
    the list is empty.
    """
    _, response = test_cli.post("/aggregator/list", json={"id": "some_id", "list": {}})

    assert response.status == 400
    assert response.json["message"] == "`list` must not be empty"


def test_sanic_post_list(test_cli):
    """
    This test checks that the post_list endpoint returns the correct data when
    the list is missing.
    """
    _, response = test_cli.post(
        "/aggregator/list", json={"id": "some_id", "list": {"peer": 1}}
    )

    assert response.status == 200


def test_sanic_get_list(test_cli):
    """
    This test checks that the get_list endpoint returns the correct data.
    """
    _, response = test_cli.get("/aggregator/list")

    assert response.status == 200
    assert isinstance(response.json, dict)


def test_sanic_post_to_db(test_cli):  # TODO: this still need to be implemented
    """
    This test checks that the post_to_db endpoint works and is able to insert data into
    the database.
    """
    _, response = test_cli.get("/aggregator/to_db")

    assert response.status == 500


def test_sanic_post_balance(test_cli):
    """
    This test checks that the post_balances endpoint returns the correct data when
    nothing is missing.
    """
    _, response = test_cli.post(
        "/aggregator/balance", json={"id": "some_id", "balances": {"xdai": 1}}
    )

    assert response.status == 200


def test_sanic_post_balance_id_missing(test_cli):
    """
    This test checks that the post_balances endpoint returns the correct data when
    the id is missing.
    """
    _, response = test_cli.post("/aggregator/balance", json={"balances": {"xdai": 1}})

    assert response.status == 400
    assert response.json["message"] == "`id` key not in body"


def test_sanic_post_balance_id_wrong_type(test_cli):
    """
    This test checks that the post_balances endpoint returns the correct data when
    the id is not a string.
    """
    _, response = test_cli.post(
        "/aggregator/balance", json={"id": 123, "balances": {"xdai": 1}}
    )

    assert response.status == 400
    assert response.json["message"] == "`id` must be a string"


def test_sanic_post_balance_balances_missing(test_cli):
    """
    This test checks that the post_balances endpoint returns the correct data when
    the balances are missing.
    """
    _, response = test_cli.post("/aggregator/balance", json={"id": "some_id"})

    assert response.status == 400
    assert response.json["message"] == "`balances` key not in body"


def test_sanic_post_balance_balances_wrong_type(test_cli):
    """
    This test checks that the post_balances endpoint returns the correct data when
    the balances are not a dict.
    """
    _, response = test_cli.post(
        "/aggregator/balance", json={"id": "some_id", "balances": 123}
    )

    assert response.status == 400
    assert response.json["message"] == "`balances` must be a dict"
